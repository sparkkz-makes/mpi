"""
Chassis Driver Node — merged motor + gimbal command generation.

Replaces the former motor_driver and gimbal_driver nodes (merged in the
2026-07 refactor). One node owns the 50 Hz steady-state timers for both
the drive wheels and the pan/tilt gimbal:

    /cmd_vel (Twist)        ──► Mecanum inverse kinematics ──► /motor_cmd
    /gimbal_vel (Twist)     ──► rate-control integrator      ──► /gimbal_cmd
    /gimbal_recenter (Empty)──► snap-to-center one-shot      ──► /gimbal_cmd

This node is transport-agnostic: it does NOT open the serial port and
contains no e-stop/gamepad logic (that lives in teleop_manager). It is a
pure function of its input topics, which makes it unit-testable without
hardware. The serial_driver gateway subscribes to /motor_cmd and
/gimbal_cmd and forwards frames to the RRC Lite board.

Kinematic model (X-configuration Mecanum, ABAB roller pattern):
    v_FL = (v_x - v_y - ω·(l + w)) / r
    v_FR = (v_x + v_y + ω·(l + w)) / r
    v_RL = (v_x + v_y - ω·(l + w)) / r
    v_RR = (v_x - v_y + ω·(l + w)) / r

where:
    v_x = linear.x  (forward, m/s)
    v_y = linear.y  (strafe left, m/s — ROS REP-103 convention)
    ω   = angular.z (turn CCW, rad/s)
    l   = wheel_base / 2, w = track_width / 2, r = wheel_radius

Safety: a watchdog stops publishing motion commands (publishes zero
speeds instead) if no /cmd_vel arrives within watchdog_timeout seconds.
Because the RRC Lite firmware has no command timeout of its own, the
steady 50 Hz zero-speed stream is what actually parks the wheels.

Gimbal rate control:
    - Stick deflection sets the *rate* of servo rotation, not the
      absolute angle. The integrator accumulates pulse width over time.
    - Rate → 0 (stick released, or teleop e-stop zeroes /gimbal_vel):
      the servo HOLDS its last position.
    - /gimbal_recenter: snaps both servos back to center with a smooth
      motion_time.

Usage:
    ros2 run mentorpi_driver chassis_driver
"""

import math

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Empty

from mentorpi_msgs.msg import MotorCommand, ServoCommand

from .logging_utils import NodeLogger, resilient_spin


class ChassisDriverNode(Node):
    """Translates /cmd_vel and /gimbal_vel into RRC command messages."""

    def __init__(self):
        super().__init__('chassis_driver')

        # ── Parameters: chassis geometry ─────────────────────────────
        # Robot geometry (used to convert m/s → wheel r/s)
        #   wheel_radius : radius of each Mecanum wheel (m)
        #   track_width  : left-to-right distance between wheel centres (m)
        #   wheel_base   : front-to-back distance between wheel centres (m)
        self.declare_parameter('wheel_radius', 0.0325)   # metres
        self.declare_parameter('track_width', 0.10)       # metres
        self.declare_parameter('wheel_base', 0.10)        # metres

        # Motor IDs on the RRC Lite (0-3), ordered: [FL, FR, RL, RR].
        # Note: the firmware uses 0-indexed motor IDs, not 1-4 as the
        # protocol doc implies.  Sending ID 4 crashes the board.
        # Physical mapping (verified by sequential spin test):
        #   0 = Front Left, 1 = Rear Left, 2 = Front Right, 3 = Rear Right
        self.declare_parameter('motor_ids', [0, 2, 1, 3])

        # Motors that are physically mirrored and need direction inversion
        # for positive speed = forward on all wheels.
        # Order matches motor_ids: [FL, FR, RL, RR]
        self.declare_parameter('invert_motors', [True, False, True, False])

        # Watchdog: publish zero speeds if no cmd_vel in this many seconds.
        self.declare_parameter('watchdog_timeout', 0.5)

        # Maximum wheel speed (r/s) — safety clamp
        self.declare_parameter('max_wheel_speed', 2.0)

        # Command publish rate (Hz) — keeps the RRC fed with fresh frames.
        self.declare_parameter('cmd_rate_hz', 50.0)

        # ── Parameters: gimbal ───────────────────────────────────────
        # Servo IDs on the RRC Lite (1 = pan, 2 = tilt; verified by
        # physical discovery, see docs/vault/mpi/Slice-6/).
        self.declare_parameter('pan_servo_id', 1)
        self.declare_parameter('tilt_servo_id', 2)

        # Pulse widths in µs. 500-2500 = 0°-180°, 1500 = 90° (center).
        self.declare_parameter('pan_center_pulse', 1500)
        self.declare_parameter('tilt_center_pulse', 1500)
        self.declare_parameter('pan_min_pulse', 1000)
        self.declare_parameter('pan_max_pulse', 2000)
        self.declare_parameter('tilt_min_pulse', 1000)
        self.declare_parameter('tilt_max_pulse', 2000)

        # Max rotation rate at full stick deflection (µs per second).
        self.declare_parameter('pan_max_rate', 1000.0)
        self.declare_parameter('tilt_max_rate', 1000.0)

        # Stick deadzone: |rate| < deadzone → 0 (hold position).
        self.declare_parameter('deadzone', 0.05)

        # Servo motion time (ms) for steady-state tracking ticks and for
        # the recenter snap.
        self.declare_parameter('motion_time_ms', 20)
        self.declare_parameter('recenter_motion_ms', 300)

        self.declare_parameter('log_level', 'info')

        # ── Load parameters ──────────────────────────────────────────
        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.track_width = self.get_parameter('track_width').value
        self.wheel_base = self.get_parameter('wheel_base').value
        self.motor_ids = list(self.get_parameter('motor_ids').value)
        self.invert_motors = list(self.get_parameter('invert_motors').value)
        self.watchdog_timeout = self.get_parameter('watchdog_timeout').value
        self.max_wheel_speed = self.get_parameter('max_wheel_speed').value
        cmd_rate = float(self.get_parameter('cmd_rate_hz').value)

        self.pan_id = int(self.get_parameter('pan_servo_id').value)
        self.tilt_id = int(self.get_parameter('tilt_servo_id').value)
        self.pan_center = int(self.get_parameter('pan_center_pulse').value)
        self.tilt_center = int(self.get_parameter('tilt_center_pulse').value)
        self.pan_min = int(self.get_parameter('pan_min_pulse').value)
        self.pan_max = int(self.get_parameter('pan_max_pulse').value)
        self.tilt_min = int(self.get_parameter('tilt_min_pulse').value)
        self.tilt_max = int(self.get_parameter('tilt_max_pulse').value)
        self.pan_max_rate = float(self.get_parameter('pan_max_rate').value)
        self.tilt_max_rate = float(self.get_parameter('tilt_max_rate').value)
        self.deadzone = float(self.get_parameter('deadzone').value)
        self.motion_time_ms = int(self.get_parameter('motion_time_ms').value)
        self.recenter_motion_ms = int(
            self.get_parameter('recenter_motion_ms').value
        )
        log_level = self.get_parameter('log_level').value

        # Pre-compute the kinematic constant: K = (l + w), the
        # half-diagonal from the chassis centre to each wheel.
        self._kinematic_K = (self.wheel_base + self.track_width) / 2.0

        self.log = NodeLogger(self, level=log_level)

        # ── State ────────────────────────────────────────────────────
        self.last_twist = Twist()  # defaults to all zeros (stopped)
        self.last_cmd_time = self.get_clock().now()
        self.is_stopped = True
        self._tick_count = 0

        # Gimbal integrator state — start at center (known position).
        self.pan_pulse = self.pan_center
        self.tilt_pulse = self.tilt_center
        self.pan_rate = 0.0
        self.tilt_rate = 0.0

        self.log.info(
            f'ChassisDriverNode starting (publishes /motor_cmd + '
            f'/gimbal_cmd).'
        )
        self.log.info(
            f'  chassis: wheel_radius={self.wheel_radius} m, '
            f'track_width={self.track_width} m, '
            f'wheel_base={self.wheel_base} m, '
            f'K=(l+w)={self._kinematic_K:.4f} m, '
            f'motor_ids={self.motor_ids}, '
            f'invert_motors={self.invert_motors}, '
            f'max_wheel_speed={self.max_wheel_speed} r/s'
        )
        self.log.info(
            f'  gimbal: pan_id={self.pan_id}, tilt_id={self.tilt_id}, '
            f'pan=[{self.pan_min}-{self.pan_max}]µs '
            f'(center {self.pan_center}), '
            f'tilt=[{self.tilt_min}-{self.tilt_max}]µs '
            f'(center {self.tilt_center}), '
            f'rates={self.pan_max_rate}/{self.tilt_max_rate} µs/s, '
            f'cmd_rate={cmd_rate} Hz'
        )

        # ── ROS2 interface ───────────────────────────────────────────
        self.motor_cmd_pub = self.create_publisher(
            MotorCommand, '/motor_cmd', 10
        )
        self.gimbal_cmd_pub = self.create_publisher(
            ServoCommand, '/gimbal_cmd', 10
        )

        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )
        self.gimbal_vel_sub = self.create_subscription(
            Twist, '/gimbal_vel', self.gimbal_vel_callback, 10
        )
        self.recenter_sub = self.create_subscription(
            Empty, '/gimbal_recenter', self.recenter_callback, 10
        )

        # Move the gimbal to its known center position on startup (also
        # confirms the command path to the board works end-to-end).
        self._publish_gimbal(self.recenter_motion_ms)

        # Single fixed-rate timer drives both motor and gimbal output.
        self._dt = 1.0 / cmd_rate
        self.command_timer = self.create_timer(self._dt, self.tick)

    # ── Kinematics ──────────────────────────────────────────────────

    def twist_to_wheel_speeds(self, twist: Twist):
        """
        Convert a Twist message to per-wheel speeds in r/s using full
        Mecanum inverse kinematics (X-configuration, ABAB roller pattern).

        Wheel speed equations (m/s at the wheel contact point):
            v_FL = v_x - v_y - ω·K
            v_FR = v_x + v_y + ω·K
            v_RL = v_x + v_y - ω·K
            v_RR = v_x - v_y + ω·K

        Sign convention assumes an X-pattern Mecanum layout:
            FL ╲ ╱ FR      (FL roller ↖, FR roller ↗)
            RL ╱ ╲ RR      (RL roller ↙, RR roller ↘)
        Positive v_y (strafe left) drives FL & RR backward, FR & RL forward.

        Returns:
            List of (motor_id, speed_rps) tuples in motor_ids order
            [FL, FR, RL, RR].
        """
        v_x = twist.linear.x          # m/s, forward
        v_y = twist.linear.y          # m/s, strafe left (REP-103)
        omega = twist.angular.z       # rad/s, CCW turn

        K = self._kinematic_K

        # Per-wheel linear velocity at the contact point (m/s)
        v_fl = v_x - v_y - omega * K
        v_fr = v_x + v_y + omega * K
        v_rl = v_x + v_y - omega * K
        v_rr = v_x - v_y + omega * K

        # Convert m/s → revolutions per second:  rps = v / (2π * r)
        circumference = 2.0 * math.pi * self.wheel_radius
        rps_fl = v_fl / circumference
        rps_fr = v_fr / circumference
        rps_rl = v_rl / circumference
        rps_rr = v_rr / circumference

        # Clamp each wheel to the safe maximum (preserves direction)
        clamp = lambda s: max(-self.max_wheel_speed,
                              min(self.max_wheel_speed, s))
        raw_speeds = [
            clamp(rps_fl),   # FL
            clamp(rps_fr),   # FR
            clamp(rps_rl),   # RL
            clamp(rps_rr),   # RR
        ]

        # Apply per-motor direction inversion (left side is mirrored on
        # this chassis — see docs/vault/mpi/Slice-3/Motor-Mapping-Discovery.md)
        wheel_speeds = []
        for motor_id, speed, invert in zip(
            self.motor_ids, raw_speeds, self.invert_motors
        ):
            if invert:
                speed = -speed
            wheel_speeds.append((motor_id, speed))

        return wheel_speeds

    # ── Publishing helpers ───────────────────────────────────────────

    def _publish_motors(self, wheel_speeds) -> None:
        """Publish per-wheel speeds on /motor_cmd."""
        msg = MotorCommand()
        msg.motor_ids = [int(mid) for mid, _ in wheel_speeds]
        msg.speeds_rps = [float(spd) for _, spd in wheel_speeds]
        self.motor_cmd_pub.publish(msg)

    def _publish_gimbal(self, motion_time_ms: int) -> None:
        """Publish current pan/tilt pulse widths on /gimbal_cmd."""
        msg = ServoCommand()
        msg.servo_ids = [self.pan_id, self.tilt_id]
        msg.pulses_us = [int(self.pan_pulse), int(self.tilt_pulse)]
        msg.motion_time_ms = int(motion_time_ms)
        self.gimbal_cmd_pub.publish(msg)

    # ── Callbacks ────────────────────────────────────────────────────

    def cmd_vel_callback(self, msg: Twist):
        """Store the latest /cmd_vel (published by teleop_manager at 50 Hz;
        already zeroed when e-stopped, so no button handling here)."""
        self.last_cmd_time = self.get_clock().now()

        # Log state transitions (stopped → moving)
        is_moving = (
            abs(msg.linear.x) > 0.001
            or abs(msg.linear.y) > 0.001
            or abs(msg.angular.z) > 0.001
        )
        if self.is_stopped and is_moving:
            self.log.info(
                f'Received movement command: v_x={msg.linear.x:.2f} m/s, '
                f'v_y={msg.linear.y:.2f} m/s, '
                f'ω={msg.angular.z:.2f} rad/s'
            )
        self.last_twist = msg

    def gimbal_vel_callback(self, msg: Twist) -> None:
        """Store the latest gimbal rate commands.
        linear.x = pan rate ([-1,1]), linear.y = tilt rate ([-1,1])."""
        self.pan_rate = self._apply_deadzone(msg.linear.x)
        self.tilt_rate = self._apply_deadzone(msg.linear.y)

    def recenter_callback(self, msg) -> None:
        """Snap both servos to center with a smooth motion time."""
        self.pan_pulse = self.pan_center
        self.tilt_pulse = self.tilt_center
        self._publish_gimbal(self.recenter_motion_ms)
        self.log.info(
            f'Recenter: pan→{self.pan_center}µs, tilt→{self.tilt_center}µs '
            f'(motion {self.recenter_motion_ms} ms)'
        )

    def _apply_deadzone(self, value: float) -> float:
        """Zero out small stick deflections within the deadzone."""
        if abs(value) < self.deadzone:
            return 0.0
        return value

    # ── Fixed-rate tick (motors + gimbal) ────────────────────────────

    def tick(self):
        """50 Hz: send the latest motor command and step the gimbal
        integrator. Keeps the RRC board fed with fresh frames — this
        stream of zero-speed commands is also the watchdog stop, since
        the board firmware has no timeout of its own."""
        self._tick_count += 1
        elapsed = (self.get_clock().now() - self.last_cmd_time).nanoseconds / 1e9

        # Heartbeat: log status every 5 seconds. INFO only when moving.
        if self._tick_count % 250 == 0:
            status = 'STOPPED' if self.is_stopped else 'RUNNING'
            heartbeat = (
                f'Heartbeat: {status}, '
                f'last_cmd={elapsed:.3f}s ago, '
                f'v_x={self.last_twist.linear.x:.2f}, '
                f'v_y={self.last_twist.linear.y:.2f}, '
                f'ω={self.last_twist.angular.z:.2f}'
            )
            is_moving = (
                abs(self.last_twist.linear.x) > 0.001
                or abs(self.last_twist.linear.y) > 0.001
                or abs(self.last_twist.angular.z) > 0.001
            )
            if is_moving:
                self.log.info(heartbeat)
            else:
                self.log.debug(heartbeat)

        # ── Motors ──────────────────────────────────────────────────
        if elapsed > self.watchdog_timeout:
            if not self.is_stopped:
                self.log.warning(
                    f'Watchdog: no cmd_vel for {elapsed:.3f}s — '
                    f'stopping motors'
                )
            zero = [(mid, 0.0) for mid in self.motor_ids]
            self._publish_motors(zero)
            self.is_stopped = True
        else:
            wheel_speeds = self.twist_to_wheel_speeds(self.last_twist)
            self._publish_motors(wheel_speeds)
            self.is_stopped = False

        # ── Gimbal integrator ───────────────────────────────────────
        clamp = lambda v, lo, hi: max(lo, min(hi, v))
        self.pan_pulse = clamp(
            int(self.pan_pulse + self.pan_rate * self.pan_max_rate * self._dt),
            self.pan_min, self.pan_max,
        )
        self.tilt_pulse = clamp(
            int(self.tilt_pulse + self.tilt_rate * self.tilt_max_rate * self._dt),
            self.tilt_min, self.tilt_max,
        )
        self._publish_gimbal(self.motion_time_ms)

    # ── Shutdown ─────────────────────────────────────────────────────

    def destroy_node(self):
        """Publish zero speeds + park the gimbal before shutting down."""
        try:
            self._publish_motors([(mid, 0.0) for mid in self.motor_ids])
            self.pan_pulse = self.pan_center
            self.tilt_pulse = self.tilt_center
            self._publish_gimbal(self.recenter_motion_ms)
            self.log.info('Motors zeroed and gimbal parked on shutdown.')
        except Exception as e:
            self.log.error(f'Error during shutdown: {e}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ChassisDriverNode()
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
