"""
Serial Driver Node for RRC Lite — the single serial gateway.

This node owns the serial connection to the RRC Lite controller board
(STM32F407VET6, UART @ 1 Mbps over /dev/ttyACM0). All other nodes
(motor_driver, gimbal_driver, future actuator nodes) are transport-
agnostic: they publish high-level command topics, and this node
translates them into RRC Lite protocol frames and writes them to the
serial port.

This is the only node that imports `serial` and `RRCLiteProtocol`.
Swapping the controller board for a different one would only require
changing this single node.

Topic interface (all sensor_msgs/JointState):
    /motor_cmd  — name=[motor_id, ...], velocity=[speed_rps, ...]
                  → RRCLiteProtocol.cmd_motor_multiple
    /gimbal_cmd — name=[servo_id, ...], position=[pulse_us, ...]
                  → RRCLiteProtocol.cmd_pwm_servo_several
                  (effort field, if present, = motion_time_ms; default 20)

Legacy (kept for Slice 1 testing):
    /test_led   — std_msgs/String → blinks LED 1 (proof-of-life)

Concurrency: callbacks are serialized by the default single-threaded
executor, so serial_conn.write() calls do not interleave. If a
MultiThreadedExecutor is ever adopted, wrap _send_frame() in a lock.
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from .logging_utils import NodeLogger, resilient_spin
from .protocol import RRCLiteProtocol


# Default motion time (ms) for servo commands when the producer doesn't
# specify one via the JointState.effort field.
DEFAULT_SERVO_MOTION_MS = 20


class SerialDriverNode(Node):
    """ROS2 gateway node: high-level command topics → RRC Lite serial frames."""

    def __init__(self):
        super().__init__('serial_driver')

        # ── Parameters ───────────────────────────────────────────────
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)
        self.declare_parameter('log_level', 'info')

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        log_level = self.get_parameter('log_level').value

        self.log = NodeLogger(self, level=log_level)

        # ── Serial connection ───────────────────────────────────────
        # Owned exclusively by this node. No other node should open
        # /dev/ttyACM0 — they publish command topics instead.
        import serial as pyserial
        try:
            self.serial_conn = pyserial.Serial(
                port,
                baudrate,
                bytesize=pyserial.EIGHTBITS,
                parity=pyserial.PARITY_NONE,
                stopbits=pyserial.STOPBITS_ONE,
                timeout=0.02,  # 20ms read timeout (non-blocking reads)
            )
            self.log.info(
                f'Serial port {port} opened @ {baudrate} baud. '
                f'Gateway ready.'
            )
        except Exception as e:  # pyserial.SerialException + others
            self.log.error(f'Failed to open serial port {port}: {e}')
            self.serial_conn = None

        # ── Subscribers (command topics) ────────────────────────────
        # Each callback builds a frame via RRCLiteProtocol and writes it.
        self.motor_sub = self.create_subscription(
            JointState, '/motor_cmd', self.motor_cmd_callback, 10
        )
        self.gimbal_sub = self.create_subscription(
            JointState, '/gimbal_cmd', self.gimbal_cmd_callback, 10
        )

        # Legacy Slice 1 test channel (LED blink from CLI).
        self.test_led_sub = self.create_subscription(
            String, '/test_led', self.test_led_callback, 10
        )

    # ── Low-level send ──────────────────────────────────────────────

    def _send_frame(self, frame: bytes, context: str = '') -> None:
        """Write a pre-built frame to the serial port."""
        if not self.serial_conn:
            self.log.warn(
                f'Serial connection not active; dropped {context} frame.'
            )
            return
        self.serial_conn.write(frame)
        self.log.debug(f'TX {context}: {frame.hex()}')

    # ── Command callbacks ───────────────────────────────────────────

    def motor_cmd_callback(self, msg: JointState) -> None:
        """
        /motor_cmd → multi-motor speed command.

        Expects JointState with:
            name:     list of motor id strings (e.g. ['0','1','2','3'])
            velocity: list of speeds in r/s (same order)
        """
        if not msg.name:
            return
        try:
            motor_data = [
                (int(n), float(v))
                for n, v in zip(msg.name, msg.velocity)
            ]
        except (ValueError, TypeError) as e:
            self.log.error(f'/motor_cmd parse error: {e} — msg={msg}')
            return

        frame = RRCLiteProtocol.cmd_motor_multiple(motor_data)
        self._send_frame(frame, context=f'motor({len(motor_data)})')

    def gimbal_cmd_callback(self, msg: JointState) -> None:
        """
        /gimbal_cmd → multi-servo pulse-width command.

        Expects JointState with:
            name:     list of servo id strings (e.g. ['1','2'])
            position: list of pulse widths in µs (500-2500 = 0°-180°)
            effort:   optional single motion_time_ms (applies to all
                      servos in this message); defaults to 20 ms.
        """
        if not msg.name:
            return
        try:
            servo_data = [
                (int(n), int(p))
                for n, p in zip(msg.name, msg.position)
            ]
        except (ValueError, TypeError) as e:
            self.log.error(f'/gimbal_cmd parse error: {e} — msg={msg}')
            return

        motion_time_ms = DEFAULT_SERVO_MOTION_MS
        if msg.effort:
            motion_time_ms = int(msg.effort[0])

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