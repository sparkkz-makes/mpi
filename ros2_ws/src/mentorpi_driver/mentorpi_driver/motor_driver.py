"""
Motor Driver Node — Slice 3

This ROS2 node bridges the gap between high-level velocity commands (/cmd_vel)
and the low-level RRC Lite motor controller. It subscribes to Twist messages,
converts them into per-wheel speeds (in revolutions per second), and sends
multi-motor commands over serial.

For Slice 3, the kinematics are a simple differential-drive model:
    - linear.x  → all wheels forward/backward
    - angular.z → left wheels and right wheels in opposite directions

Full Mecanum inverse kinematics (strafing) will be added in Slice 5.

Safety: a watchdog timer stops all motors if no /cmd_vel message is received
within the timeout period (default 0.5 s). This prevents runaway behaviour if
the teleop node crashes or the network drops.

Usage:
    ros2 run mentorpi_driver motor_driver
    ros2 run mentorpi_driver motor_driver --ros-args -p port:=/dev/ttyUSB0
"""

import math
import serial
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy

from .logging_utils import NodeLogger
from .protocol import RRCLiteProtocol


class MotorDriverNode(Node):
    """Translates /cmd_vel Twist commands into RRC Lite motor commands."""

    def __init__(self):
        super().__init__('motor_driver')

        # ── Parameters ────────────────────────────────────────────────
        # Serial connection
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)

        # Robot geometry (used to convert m/s → wheel r/s)
        self.declare_parameter('wheel_radius', 0.0325)   # metres
        self.declare_parameter('track_width', 0.10)       # metres (left-to-right)

        # Motor IDs on the RRC Lite (0-3), ordered: [FL, FR, RL, RR].
        # Note: the firmware uses 0-indexed motor IDs, not 1-4 as the
        # protocol doc implies.  Sending ID 4 crashes the board.
        # Physical mapping (verified by sequential spin test):
        #   0 = Front Left, 1 = Rear Left, 2 = Front Right, 3 = Rear Right
        self.declare_parameter('motor_ids', [0, 2, 1, 3])

        # Motors that are physically mirrored and need direction inversion
        # for positive speed = forward on all wheels.
        # Order matches motor_ids: [FL, FR, RL, RR]
        #   FL (id 0) → invert, FR (id 2) → ok, RL (id 1) → invert, RR (id 3) → ok
        self.declare_parameter('invert_motors', [True, False, True, False])

        # Watchdog: stop motors if no cmd_vel in this many seconds.
        # teleop_twist_keyboard sends repeated messages while a key is held
        # (at the keyboard auto-repeat rate), so a short timeout is fine.
        self.declare_parameter('watchdog_timeout', 0.5)

        # Maximum wheel speed (r/s) — safety clamp
        self.declare_parameter('max_wheel_speed', 2.0)

        # Emergency-stop button index on the /joy message (0 = A, 3 = X)
        self.declare_parameter('emergency_stop_button', 3)

        # Logging verbosity: debug, info, warn, error, fatal
        self.declare_parameter('log_level', 'info')

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.track_width = self.get_parameter('track_width').value
        self.motor_ids = list(self.get_parameter('motor_ids').value)
        self.invert_motors = list(self.get_parameter('invert_motors').value)
        self.watchdog_timeout = self.get_parameter('watchdog_timeout').value
        self.max_wheel_speed = self.get_parameter('max_wheel_speed').value
        self.emergency_stop_button = self.get_parameter(
            'emergency_stop_button'
        ).value
        log_level = self.get_parameter('log_level').value

        # Dual ROS2 + developer-friendly file logger
        self.log = NodeLogger(self, level=log_level)

        self.log.info(
            f'MotorDriverNode starting. Port={port}, Baud={baudrate}'
        )
        self.log.info(
            f'  wheel_radius={self.wheel_radius} m, '
            f'track_width={self.track_width} m'
        )
        self.log.info(
            f'  motor_ids={self.motor_ids}, '
            f'invert_motors={self.invert_motors}, '
            f'max_wheel_speed={self.max_wheel_speed} r/s, '
            f'emergency_stop_button={self.emergency_stop_button}'
        )

        # ── Serial connection ───────────────────────────────────────
        try:
            self.serial_conn = serial.Serial(
                port,
                baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02,
            )
            self.log.info('Serial port opened successfully.')
        except serial.SerialException as e:
            self.log.error(f'Failed to open serial port: {e}')
            self.serial_conn = None

        # ── ROS2 interface ───────────────────────────────────────────
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )
        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10
        )

        # Fixed-rate command timer — re-sends the last command at 50 Hz.
        # This ensures the RRC Lite keeps receiving commands.  If the node
        # dies, the board stops getting commands (but may keep the last
        # one — see the safety note below).
        self.last_twist = Twist()  # Defaults to all zeros (stopped)
        self.last_cmd_time = self.get_clock().now()
        self.command_timer = self.create_timer(0.02, self.command_callback)

        # Track whether we are currently stopped (to avoid spamming stop cmds)
        self.is_stopped = True

        # Emergency stop state. Once set, cmd_vel is ignored and stop
        # frames are sent repeatedly until the user toggles the e-stop
        # button again.
        self.emergency_stop = False
        self._prev_estop_button = 0

        # Heartbeat counter for periodic status logging
        self._tick_count = 0

    # ── Kinematics ──────────────────────────────────────────────────

    def twist_to_wheel_speeds(self, twist: Twist):
        """
        Convert a Twist message to per-wheel speeds in r/s.

        Differential-drive model (simplified for 4-wheel skid steer):
            v_left  = (v - ω * W/2) / r
            v_right = (v + ω * W/2) / r

        where:
            v = linear.x   (m/s)
            ω = angular.z  (rad/s)
            W = track_width (m)
            r = wheel_radius (m)

        All four left wheels get v_left, all four right wheels get v_right.
        (Full Mecanum kinematics with strafing comes in Slice 5.)

        Returns:
            List of (motor_id, speed_rps) tuples.
        """
        v = twist.linear.x          # m/s
        omega = twist.angular.z     # rad/s

        # Linear velocity of each side (m/s)
        v_left = v - omega * self.track_width / 2.0
        v_right = v + omega * self.track_width / 2.0

        # Convert m/s → revolutions per second:  rps = v / (2π * r)
        circumference = 2.0 * math.pi * self.wheel_radius
        rps_left = v_left / circumference
        rps_right = v_right / circumference

        # Clamp to safe maximum
        rps_left = max(-self.max_wheel_speed,
                       min(self.max_wheel_speed, rps_left))
        rps_right = max(-self.max_wheel_speed,
                        min(self.max_wheel_speed, rps_right))

        # motor_ids order: [FL, FR, RL, RR]
        # FL and RL are left side; FR and RR are right side.
        raw_speeds = [
            rps_left,    # FL
            rps_right,   # FR
            rps_left,    # RL
            rps_right,   # RR
        ]

        # Apply per-motor direction inversion (right side is mirrored)
        wheel_speeds = []
        for motor_id, speed, invert in zip(
            self.motor_ids, raw_speeds, self.invert_motors
        ):
            if invert:
                speed = -speed
            wheel_speeds.append((motor_id, speed))

        return wheel_speeds

    # ── Command sending ─────────────────────────────────────────────

    def send_wheel_speeds(self, wheel_speeds):
        """Build and send a multi-motor command."""
        if not self.serial_conn:
            return

        cmd = RRCLiteProtocol.cmd_motor_multiple(wheel_speeds)
        self.serial_conn.write(cmd)
        self.log.debug(
            f'Serial TX: {cmd.hex()}  speeds={wheel_speeds}'
        )

    def stop_all_motors(self, repeat: int = 1, flush: bool = False):
        """Send a stop command for all motors, optionally repeated."""
        if not self.serial_conn:
            return
        # Bitmask 0x0F = motors 1, 2, 3, 4
        cmd = RRCLiteProtocol.cmd_motor_stop_several(0x0F)
        for _ in range(repeat):
            self.serial_conn.write(cmd)
        if flush:
            # Only flush on emergency paths so we do not discard queued
            # commands from other nodes (LED, servo, buzzer, etc.).
            self.serial_conn.flush()
        self.is_stopped = True
        self.log.debug(f'Serial TX stop x{repeat}: {cmd.hex()}')

    # ── Callbacks ────────────────────────────────────────────────────

    def cmd_vel_callback(self, msg: Twist):
        """Called when a Twist message arrives on /cmd_vel."""
        self.last_cmd_time = self.get_clock().now()

        if self.emergency_stop:
            # Ignore motion commands while e-stopped, but keep the time fresh
            # so the watchdog does not also fire.
            return

        # Log state transitions (stopped → moving)
        was_stopped = self.is_stopped
        is_moving = abs(msg.linear.x) > 0.001 or abs(msg.angular.z) > 0.001
        if was_stopped and is_moving:
            self.log.info(
                f'Received movement command: v={msg.linear.x:.2f} m/s, '
                f'ω={msg.angular.z:.2f} rad/s'
            )
        self.log.debug(
            f'cmd_vel: v={msg.linear.x:.3f}, vy={msg.linear.y:.3f}, '
            f'ω={msg.angular.z:.3f}'
        )
        self.last_twist = msg

    def joy_callback(self, msg: Joy):
        """Watch the emergency-stop button (default X / button 3)."""
        buttons = msg.buttons
        if len(buttons) <= self.emergency_stop_button:
            return

        pressed = buttons[self.emergency_stop_button]
        # Toggle emergency stop on rising edge.
        if pressed and not self._prev_estop_button:
            self.emergency_stop = not self.emergency_stop
            if self.emergency_stop:
                self.log.warn(
                    'EMERGENCY STOP activated — ignoring /cmd_vel and '
                    'sending repeated stop frames'
                )
                # Immediately blast stop frames to the RRC.
                self.stop_all_motors(repeat=5, flush=True)
            else:
                self.log.warn('Emergency stop cleared — resuming normal control')
                self.last_cmd_time = self.get_clock().now()
        self._prev_estop_button = pressed

    def command_callback(self):
        """Fixed-rate timer (50 Hz): send the latest command or stop."""
        self._tick_count += 1
        elapsed = (self.get_clock().now() - self.last_cmd_time).nanoseconds / 1e9

        # Heartbeat: log status every 5 seconds (250 ticks at 50 Hz).
        # Only log at INFO when moving; otherwise DEBUG to avoid idle noise.
        if self._tick_count % 250 == 0:
            status = 'STOPPED' if self.is_stopped else 'RUNNING'
            heartbeat = (
                f'Heartbeat: {status}, '
                f'last_cmd={elapsed:.3f}s ago, '
                f'v={self.last_twist.linear.x:.2f}, '
                f'ω={self.last_twist.angular.z:.2f}'
            )
            if self.is_stopped:
                self.log.debug(heartbeat)
            else:
                self.log.info(heartbeat)

        if elapsed > self.watchdog_timeout:
            if not self.is_stopped:
                self.log.warn(
                    f'Watchdog: no cmd_vel for {elapsed:.3f}s — stopping motors'
                )
                # Send several stop frames; the RRC can miss a single one.
                # NOTE: this is a watchdog stop, not an emergency stop, so we
                # do not latch emergency_stop — releasing A and pressing it
                # again should let the user drive without toggling e-stop.
                self.stop_all_motors(repeat=5, flush=True)
            return

        if self.emergency_stop:
            self.stop_all_motors(repeat=1)
            return

        wheel_speeds = self.twist_to_wheel_speeds(self.last_twist)
        self.send_wheel_speeds(wheel_speeds)
        self.is_stopped = False

    # ── Shutdown ─────────────────────────────────────────────────────

    def destroy_node(self):
        """Stop all motors before shutting down."""
        if self.serial_conn:
            try:
                self.stop_all_motors()
                self.log.info('Motors stopped on shutdown.')
            except Exception as e:
                self.log.error(f'Error stopping motors: {e}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MotorDriverNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
