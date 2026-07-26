"""
Serial Driver Node for RRC Lite — the single serial gateway.

This node owns the serial connection to the RRC Lite controller board
(STM32F407VET6, UART @ 1 Mbps over /dev/ttyACM0, CH341 USB-serial).
All other nodes are transport-agnostic: they publish high-level command
topics, and this node translates them into RRC Lite protocol frames and
writes them to the serial port. It also DRAINS and parses everything the
board sends back (button events, IMU data, servo position responses) and
re-publishes it as ROS topics for a future telemetry UI.

This is the only node that imports `serial` and `RRCLiteProtocol`.
Swapping the controller board for a different one would only require
changing this single node.

Command topics (mentorpi_msgs):
    /motor_cmd  — MotorCommand (ids + speeds r/s)
                  → RRCLiteProtocol.cmd_motor_multiple
    /gimbal_cmd — ServoCommand (ids + pulse widths + motion time)
                  → RRCLiteProtocol.cmd_pwm_servo_several

Telemetry topics (board → host, parsed from the RX stream):
    /rrc_telemetry — RrcTelemetry: every well-formed frame, raw payload.
                     Generic channel for a future telemetry UI.
    /rrc_imu       — sensor_msgs/Imu: decoded FUNC_IMU uploads.

Legacy (kept for Slice 1 testing):
    /test_led   — std_msgs/String → blinks LED 1 (proof-of-life)

RX draining is load-bearing, not just for telemetry: the CH341
USB-serial chip can back-pressure its TX path (hanging write() in the
kernel, no exception, silent executor freeze — observed 2026-07-26) if
the host never reads the board's unsolicited upload frames. The 100 Hz
RX timer keeps the buffer drained.

Board health monitoring (added after the 2026-07-26 board-wedge incident):
  - IMU heartbeat: the board streams IMU frames continuously; if that
    stream stops for >10 s the board is wedged/dead → FATAL alarm.
    (Note: in the observed wedge mode the IMU KEPT streaming while the
    command processor was dead — stock firmware gives no reliable
    software signal for that state. A proper fix needs board firmware
    with a watchdog, which is planned future work.)
  - Servo-position probes are sent every 5 s as corroborating evidence,
    but stock firmware doesn't reliably answer reads, so missed probes
    alone only produce a one-time informational WARN.
  - The RX parser counts discarded bytes; a high discard rate with zero
    valid frames means the board is speaking garbage (wrong baud, stuck
    in bootloader) → WARN alarm.
  - Auto-reconnect: persistent read/write errors close the port and a
    1 Hz timer reopens it with exponential backoff, so a board reset
    recovers without restarting this node.

Stuck-port detector: _send_frame() timestamps every successful write;
a 2 Hz monitor logs a loud FATAL breadcrumb if no write has completed
for several seconds (see _stuck_check for its limits).

Concurrency: callbacks are serialized by the default single-threaded
executor, so serial_conn access does not interleave. If a
MultiThreadedExecutor is ever adopted, wrap _send_frame()/_rx_drain()
in a shared lock.
"""
import struct

import serial as pyserial
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String

from mentorpi_msgs.msg import MotorCommand, RrcTelemetry, ServoCommand

from .logging_utils import NodeLogger, resilient_spin
from .protocol import RRCLiteProtocol


# Default motion time (ms) for servo commands when the producer doesn't
# specify one.
DEFAULT_SERVO_MOTION_MS = 20

# How often (s) the RX drain timer runs. 100 Hz keeps the CH341 buffer
# empty without busy-spinning.
RX_DRAIN_PERIOD_S = 0.01

# Stuck-port detector: monitor timer period and the silence gap (s)
# after which we log a FATAL breadcrumb.
STUCK_CHECK_PERIOD_S = 0.5
STUCK_THRESHOLD_S = 5.0

# Function codes we decode into convenience topics (see
# docs/rrc-lite-protocol.md "Upload ..." sections).
FUNC_KEY = 6
FUNC_IMU = 7


class SerialDriverNode(Node):
    """ROS2 gateway node: command topics ↔ RRC Lite serial frames."""

    def __init__(self):
        super().__init__('serial_driver')

        # ── Parameters ───────────────────────────────────────────────
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)
        self.declare_parameter('log_level', 'info')

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        log_level = self.get_parameter('log_level').value

        self._port = port
        self._baudrate = baudrate

        self.log = NodeLogger(self, level=log_level)

        # ── Serial connection ───────────────────────────────────────
        # Owned exclusively by this node. No other node should open
        # /dev/ttyACM0 — they publish command topics instead.
        self.serial_conn = None
        self._reconnect_backoff = 1.0  # seconds; doubles on repeated failure
        self._open_serial_port()

        # ── Subscribers (command topics) ────────────────────────────
        self.motor_sub = self.create_subscription(
            MotorCommand, '/motor_cmd', self.motor_cmd_callback, 10
        )
        self.gimbal_sub = self.create_subscription(
            ServoCommand, '/gimbal_cmd', self.gimbal_cmd_callback, 10
        )

        # Legacy Slice 1 test channel (LED blink from CLI).
        self.test_led_sub = self.create_subscription(
            String, '/test_led', self.test_led_callback, 10
        )

        # ── Publishers (telemetry, board → host) ────────────────────
        # Raw channel: every well-formed frame from the board.
        self.telemetry_pub = self.create_publisher(
            RrcTelemetry, '/rrc_telemetry', 10
        )
        # Decoded convenience channel for IMU uploads.
        self.imu_pub = self.create_publisher(Imu, '/rrc_imu', 10)

        # ── RX state ────────────────────────────────────────────────
        # Byte buffer fed by the drain timer and consumed by the parser.
        self._rx_buf = bytearray()
        self._rx_bytes_total = 0
        self._rx_frames_total = 0
        self._rx_crc_errors = 0
        self._rx_discarded = 0  # bytes dropped during resync (garbage detector)

        # ── Statistics (for diagnosing serial buffer issues) ────────
        self._stats_sent = 0
        self._stats_dropped = 0
        self._stats_bytes = 0
        self._stats_errors = 0
        self.create_timer(10.0, self._log_stats)

        # ── RX drain timer (100 Hz) ─────────────────────────────────
        # Keeps the CH341 RX buffer empty and feeds the frame parser.
        # See module docstring for why this is load-bearing.
        self.create_timer(RX_DRAIN_PERIOD_S, self._rx_drain)

        # ── Stuck-port detector (2 Hz) ──────────────────────────────
        self._last_progress = self.get_clock().now()
        self._stuck_announced = False
        self.create_timer(STUCK_CHECK_PERIOD_S, self._stuck_check)

        # ── Board liveness probe (every 5 s) ────────────────────────
        # Sends a servo-position read (PWM_SERVO subcommand 0x05, servo 1)
        # and watches for the upload response (FUNC_PWM_SERVO frame with
        # subcommand 0x05 in params). NOTE 2026-07-26: the stock RRC Lite
        # firmware answers servo-position reads ONLY when the servo is
        # actively moving (or possibly never) — probes went 3× unanswered
        # on a fully healthy, driving robot. So an unanswered probe is NOT
        # used as a wedge alarm by itself; the alarm requires BOTH missed
        # probes AND a silent IMU stream (the IMU is the board's hardware
        # heartbeat — if that stops, the board is genuinely wedged).
        self._probe_outstanding = 0
        self._probe_missed = 0
        self._wedge_announced = False
        self._last_imu_time = None
        self._last_rx_frame_time = None
        self.create_timer(5.0, self._liveness_probe)

        # ── Auto-reconnect (1 Hz check) ─────────────────────────────
        # If the port has failed/disappeared (board reset, USB glitch),
        # keep trying to reopen with exponential backoff so recovery
        # doesn't need a manual node restart.
        self._reconnect_timer = self.create_timer(1.0, self._maybe_reconnect)

    # ── Port lifecycle ──────────────────────────────────────────────

    def _open_serial_port(self) -> bool:
        """(Re)open the serial port. Returns True on success.

        write_timeout: pyserial's write() is blocking by default. If the
        RRC board's UART RX buffer fills up (e.g. board hangs or can't
        drain fast enough), write() blocks indefinitely, freezing the
        executor and starving all other callbacks. A write_timeout
        ensures the call returns (with SerialTimeoutException) instead.

        timeout=0 (non-blocking reads): reads are done by the RX drain
        timer; we never want a read to block the executor.
        """
        try:
            self.serial_conn = pyserial.Serial(
                self._port,
                self._baudrate,
                bytesize=pyserial.EIGHTBITS,
                parity=pyserial.PARITY_NONE,
                stopbits=pyserial.STOPBITS_ONE,
                timeout=0,            # non-blocking reads (drained by timer)
                write_timeout=0.01,   # 10ms write timeout (non-blocking writes)
            )
            self.log.info(
                f'Serial port {self._port} opened @ {self._baudrate} baud. '
                f'Gateway ready.'
            )
            self._reconnect_backoff = 1.0
            self._rx_buf.clear()
            return True
        except Exception as e:  # pyserial.SerialException + others
            self.serial_conn = None
            self.log.error(f'Failed to open serial port {self._port}: {e}')
            return False

    def _close_serial_port(self) -> None:
        """Close the port (best-effort) and mark it disconnected."""
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None

    def _maybe_reconnect(self) -> None:
        """1 Hz: if the port is down, retry the open with backoff."""
        if self.serial_conn is not None:
            return
        now = self.get_clock().now()
        if not hasattr(self, '_next_reconnect_at'):
            self._next_reconnect_at = now
        if (now - self._next_reconnect_at).nanoseconds < 0:
            return
        self.log.warn(
            f'Attempting to reopen serial port {self._port} '
            f'(backoff {self._reconnect_backoff:.0f}s)...'
        )
        if self._open_serial_port():
            # Fresh board — probe immediately to confirm it's alive.
            self._probe_outstanding = 0
            self._probe_missed = 0
            self._wedge_announced = False
        else:
            self._reconnect_backoff = min(self._reconnect_backoff * 2, 30.0)
        self._next_reconnect_at = (
            now + rclpy.duration.Duration(seconds=self._reconnect_backoff)
        )

    # ── Board liveness probe ────────────────────────────────────────

    def _liveness_probe(self) -> None:
        """5 s: monitor board liveness via IMU heartbeat + probe responses.

        The IMU stream is the primary liveness signal: it is generated by
        hardware/peripheral polling on the board, and in the observed
        wedge mode (2026-07-26) it KEPT streaming while the command
        processor was dead — so IMU alone can't detect that wedge. Probe
        responses would detect it, but stock firmware doesn't reliably
        answer reads, so missed probes are only corroborating evidence.

        Alarm policy:
          - IMU silent > 10 s → FATAL (board dead/wedged, power-cycle).
          - Probes missed ≥ 3 AND IMU also silent → same alarm (IMU rule
            already covers it).
          - Probes missed ≥ 3 with IMU alive → single WARN noting the
            firmware quirk (informational; expected on stock firmware).
        """
        if not self.serial_conn:
            return

        # ── IMU heartbeat check ─────────────────────────────────────
        if self._last_imu_time is not None:
            imu_gap = (
                self.get_clock().now() - self._last_imu_time
            ).nanoseconds / 1e9
            if imu_gap > 10.0 and not self._wedge_announced:
                self._wedge_announced = True
                self.log.fatal(
                    f'No IMU frames from RRC board for {imu_gap:.0f}s — '
                    f'board appears wedged or dead. Power-cycle the RRC '
                    f'board (the Pi will reboot too if powered by it).'
                )
            elif imu_gap <= 10.0 and self._wedge_announced:
                self.log.info('IMU frames resumed — board recovered.')
                self._wedge_announced = False

        # ── Probe accounting (corroborating evidence only) ──────────
        if self._probe_outstanding > 0:
            self._probe_missed += self._probe_outstanding
            self._probe_outstanding = 0
            if self._probe_missed == 3:
                self.log.warn(
                    'RRC board has not answered any servo-position probes '
                    '(3 missed). NOTE: stock firmware does not reliably '
                    'answer reads — this alone is NOT a wedge indicator. '
                    'IMU stream is the liveness signal.'
                )

        # Servo 1 position read: subcommand 0x05, servo_id 1.
        frame = RRCLiteProtocol.pack_frame(
            RRCLiteProtocol.FUNC_PWM_SERVO,
            bytes([RRCLiteProtocol.PWM_SERVO_CMD_READ_POS, 1]),
        )
        self._send_frame(frame, context='probe')
        self._probe_outstanding += 1

    # ── Low-level send ──────────────────────────────────────────────

    def _send_frame(self, frame: bytes, context: str = '') -> None:
        """Write a pre-built frame to the serial port (non-blocking)."""
        if not self.serial_conn:
            self.log.warn(
                f'Serial connection not active; dropped {context} frame.'
            )
            self._stats_dropped += 1
            return
        try:
            self.serial_conn.write(frame)
            self._stats_sent += 1
            self._stats_bytes += len(frame)
            self._last_progress = self.get_clock().now()
            self._stuck_announced = False
            self.log.debug(f'TX {context}: {frame.hex()}')
        except pyserial.SerialTimeoutException:
            # Write timed out — the RRC board's UART buffer is full or
            # the board is not draining. Drop the frame and continue;
            # the next callback will retry. This prevents a blocked write
            # from freezing the executor and starving other callbacks.
            self._stats_dropped += 1
            self.log.warn(
                f'Write timeout on {context} frame — dropped '
                f'(total dropped: {self._stats_dropped}).'
            )
        except Exception as e:
            self._stats_errors += 1
            self.log.error(f'Write error on {context} frame: {e}')
            # Persistent low-level errors (ENODEV/EIO after a board reset
            # or USB glitch) mean the fd is dead — close it so the
            # auto-reconnect timer reopens the port.
            if self._stats_errors >= 5:
                self.log.warn(
                    'Too many write errors — closing port for reconnect.'
                )
                self._close_serial_port()
                self._stats_errors = 0

    def _log_stats(self) -> None:
        """Log a periodic summary of serial throughput, drops and RX."""
        rx_active = self._rx_bytes_total > 0
        if (
            self._stats_sent == 0 and self._stats_dropped == 0
            and not rx_active
        ):
            return  # nothing to report (idle)
        total = self._stats_sent + self._stats_dropped
        drop_pct = (self._stats_dropped / total * 100) if total else 0
        # Bytes per second over the 10s window.
        bps = self._stats_bytes / 10.0
        # At 1 Mbps 8N1, max throughput is ~100,000 bytes/s.
        util = (bps / 100000) * 100
        msg = (
            f'Serial stats (10s): TX sent={self._stats_sent}, '
            f'dropped={self._stats_dropped} ({drop_pct:.1f}%), '
            f'errors={self._stats_errors}, '
            f'{bps:.0f} B/s ({util:.1f}% of 1Mbps) | '
            f'RX bytes={self._rx_bytes_total}, '
            f'frames={self._rx_frames_total}, '
            f'crc_errors={self._rx_crc_errors}, '
            f'discarded={self._rx_discarded}'
        )
        garbage = (
            self._rx_discarded > 1000
            and self._rx_frames_total == 0
        )
        if garbage:
            self.log.warn(
                msg + ' — HIGH DISCARD RATE: board is speaking garbage '
                '(wrong baud? stuck in bootloader? dead UART?). '
                'Power-cycle the RRC board.'
            )
        elif self._stats_dropped > 0:
            self.log.warn(msg)
        else:
            self.log.info(msg)
        # Reset counters for the next window.
        self._stats_sent = 0
        self._stats_dropped = 0
        self._stats_bytes = 0
        self._stats_errors = 0
        self._rx_bytes_total = 0
        self._rx_frames_total = 0
        self._rx_crc_errors = 0
        self._rx_discarded = 0

    def _stuck_check(self) -> None:
        """Detect a wedged serial port / frozen write path.

        _send_frame() updates _last_progress at ~100 Hz during normal
        teleop. If this timer observes a long gap, either the robot is
        genuinely idle (no commands flowing — also a gap) or the
        executor froze inside write(). We can't distinguish the two from
        inside the same executor, so this is only a breadcrumb: during a
        real hard freeze this callback never runs, but when a *transient*
        wedge recovers it leaves a timestamped FATAL line in the log
        instead of the freeze passing silently. A resumed write clears
        the flag.
        """
        gap = (
            self.get_clock().now() - self._last_progress
        ).nanoseconds / 1e9
        if gap > STUCK_THRESHOLD_S and not self._stuck_announced:
            self._stuck_announced = True
            self.log.fatal(
                f'No serial writes completed for {gap:.1f}s — port may be '
                f'wedged (or robot idle). If the car is unresponsive, '
                f'power-cycle the RRC board.'
            )

    # ── RX drain + frame parser ─────────────────────────────────────

    def _rx_drain(self) -> None:
        """Read any pending board→host bytes and parse complete frames.

        Runs at 100 Hz. Two jobs:
          1. Keep the CH341 RX buffer drained (avoids the TX back-pressure
             wedge that froze the old implementation).
          2. Reassemble frames and re-publish them as ROS telemetry.
        """
        if not self.serial_conn:
            return
        try:
            waiting = self.serial_conn.in_waiting
            if waiting:
                chunk = self.serial_conn.read(waiting)
                self._rx_buf.extend(chunk)
                self._rx_bytes_total += len(chunk)
        except Exception as e:
            self._stats_errors += 1
            self.log.error(f'Serial read error: {e}')
            # A dead fd (board reset, USB unplug) raises here repeatedly.
            # Close so the auto-reconnect timer can reopen the port.
            self._close_serial_port()
            return
        self._parse_rx_buffer()

    def _parse_rx_buffer(self) -> None:
        """Extract complete, CRC-valid frames from _rx_buf.

        Frame format: [0xAA][0x55][Func][Len][Params...][CRC8].
        Resyncs by discarding bytes until the next 0xAA 0x55 header.
        """
        while True:
            # Resync to the frame header.
            start = self._rx_buf.find(RRCLiteProtocol.FRAME_HEADER)
            if start < 0:
                # No header in sight; keep at most one trailing byte in
                # case it is the 0xAA of a header split across reads.
                keep = 1 if self._rx_buf.endswith(b'\xaa') else 0
                dropped = len(self._rx_buf) - keep
                if dropped > 0:
                    self._rx_discarded += dropped
                    del self._rx_buf[:dropped]
                return
            if start > 0:
                self._rx_discarded += start
                del self._rx_buf[:start]

            # Need header + func + len before we know the frame size.
            if len(self._rx_buf) < 4:
                return

            func = self._rx_buf[2]
            data_len = self._rx_buf[3]
            frame_len = 2 + 1 + 1 + data_len + 1
            if len(self._rx_buf) < frame_len:
                return  # wait for the rest of the frame

            frame = bytes(self._rx_buf[:frame_len])
            del self._rx_buf[:frame_len]

            params = frame[4:-1]
            expected_crc = RRCLiteProtocol.calc_crc8(
                bytes([func, data_len]) + params
            )
            if expected_crc != frame[-1]:
                self._rx_crc_errors += 1
                self._rx_discarded += frame_len
                self.log.warn(
                    f'RX CRC error: func={func:#04x} len={data_len} '
                    f'frame={frame.hex()}'
                )
                continue

            self._rx_frames_total += 1
            self._handle_rx_frame(func, params, frame)

    def _handle_rx_frame(
        self, func: int, params: bytes, raw: bytes
    ) -> None:
        """Publish one parsed board frame on the telemetry topics."""
        msg = RrcTelemetry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.function_code = func
        msg.params = list(params)
        self.telemetry_pub.publish(msg)
        self.log.debug(f'RX func={func:#04x}: {raw.hex()}')

        # Decoded convenience topics for known upload frames.
        if func == FUNC_IMU and len(params) == 24:
            self._last_imu_time = self.get_clock().now()
            values = struct.unpack('<6f', params)
            imu = Imu()
            imu.header.stamp = msg.header.stamp
            imu.header.frame_id = 'rrc_imu'
            (imu.linear_acceleration.x,
             imu.linear_acceleration.y,
             imu.linear_acceleration.z,
             imu.angular_velocity.x,
             imu.angular_velocity.y,
             imu.angular_velocity.z) = values
            self.imu_pub.publish(imu)
        elif (
            func == RRCLiteProtocol.FUNC_PWM_SERVO
            and len(params) == 4
            and params[1] == RRCLiteProtocol.PWM_SERVO_CMD_READ_POS
        ):
            # Servo-position upload (answer to our liveness probe):
            # params = [servo_id, 0x05, pulse_lo, pulse_hi]
            self._probe_outstanding = 0
            self._probe_missed = 0
            pulse = params[2] | (params[3] << 8)
            self.log.debug(
                f'Probe response: servo {params[0]} at {pulse} µs'
            )
        elif func == FUNC_KEY and len(params) == 2:
            self.log.info(
                f'RRC button event: id={params[0]} event={params[1]:#04x}'
            )

    # ── Command callbacks ───────────────────────────────────────────

    def motor_cmd_callback(self, msg: MotorCommand) -> None:
        """/motor_cmd → multi-motor speed command frame."""
        if not msg.motor_ids:
            return
        if len(msg.motor_ids) != len(msg.speeds_rps):
            self.log.error(
                f'/motor_cmd length mismatch: {len(msg.motor_ids)} ids vs '
                f'{len(msg.speeds_rps)} speeds — dropped'
            )
            return
        motor_data = [
            (int(mid), float(spd))
            for mid, spd in zip(msg.motor_ids, msg.speeds_rps)
        ]
        frame = RRCLiteProtocol.cmd_motor_multiple(motor_data)
        self._send_frame(frame, context=f'motor({len(motor_data)})')

    def gimbal_cmd_callback(self, msg: ServoCommand) -> None:
        """/gimbal_cmd → multi-servo pulse-width command frame."""
        if not msg.servo_ids:
            return
        if len(msg.servo_ids) != len(msg.pulses_us):
            self.log.error(
                f'/gimbal_cmd length mismatch: {len(msg.servo_ids)} ids vs '
                f'{len(msg.pulses_us)} pulses — dropped'
            )
            return
        servo_data = [
            (int(sid), int(pulse))
            for sid, pulse in zip(msg.servo_ids, msg.pulses_us)
        ]
        motion_time_ms = (
            int(msg.motion_time_ms)
            if msg.motion_time_ms > 0
            else DEFAULT_SERVO_MOTION_MS
        )
        frame = RRCLiteProtocol.cmd_pwm_servo_several(
            servo_data, motion_time_ms
        )
        self._send_frame(frame, context=f'gimbal({len(servo_data)})')

    # ── Legacy ──────────────────────────────────────────────────────

    def test_led_callback(self, msg: String) -> None:
        """Slice 1 proof-of-life: blink LED 1 (100ms on/off, 5 cycles)."""
        self.log.info(f'test_led received: "{msg.data}" — blinking LED 1')
        frame = RRCLiteProtocol.cmd_led(1, 100, 100, 5)
        self._send_frame(frame, context='test_led')

    # ── Shutdown ────────────────────────────────────────────────────

    def destroy_node(self):
        """Best-effort stop-all on shutdown."""
        if self.serial_conn:
            try:
                stop = RRCLiteProtocol.cmd_motor_stop_several(0x0F)
                self.serial_conn.write(stop)
                self.log.info('Sent motor stop on shutdown.')
            except Exception as e:
                self.log.error(f'Shutdown stop failed: {e}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialDriverNode()
    try:
        resilient_spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
