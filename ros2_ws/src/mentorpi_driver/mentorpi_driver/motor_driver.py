"""
Motor Driver Node — Slice 5 (Full Mecanum Motion Control)

This ROS2 node bridges the gap between high-level velocity commands (/cmd_vel)
and per-wheel speeds. It subscribes to Twist messages, converts them into
per-wheel speeds (in revolutions per second) using full Mecanum inverse
kinematics, and publishes them on /motor_cmd (sensor_msgs/JointState).

This node is transport-agnostic: it does NOT open the serial port. The
serial_driver gateway node subscribes to /motor_cmd and forwards it to
the RRC Lite board. This separation means motor_driver can be unit-tested
without hardware, and the controller board can be swapped by changing
only serial_driver.

Kinematic model (X-configuration Mecanum, ABAB roller pattern):
    v_FL = (v_x - v_y - ω·(l + w)) / r
    v_FR = (v_x + v_y + ω·(l + w)) / r
    v_RL = (v_x + v_y - ω·(l + w)) / r
    v_RR = (v_x - v_y + ω·(l + w)) / r

where:
    v_x = linear.x  (forward, m/s)
    v_y = linear.y   (strafe left, m/s — ROS REP-103 convention)
    ω   = angular.z  (turn CCW, rad/s)
    l   = wheel_base / 2   (half length, front→centre)
    w   = track_width / 2 (half width, centre→side)
    r   = wheel_radius

All three motion components are combined linearly, so the robot can
drive forward while strafing and turning simultaneously (e.g. a 45°
diagonal is just forward + strafe at equal magnitude).

Safety: a watchdog timer stops all motors if no /cmd_vel message is
received within the timeout period (default 0.5 s). This prevents runaway
behaviour if the teleop node crashes or the network drops.

Usage:
    ros2 run mentorpi_driver motor_driver
    ros2 run mentorpi_driver motor_driver --ros-args -p port:=/dev/ttyUSB0
"""

import math
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy, JointState

from .logging_utils import NodeLogger, resilient_spin


class MotorDriverNode(Node):
    """Translates /cmd_vel Twist commands into RRC Lite motor commands."""

    def __init__(self):
        super().__init__('motor_driver')

        # ── Parameters ────────────────────────────────────────────────
        # (Serial connection is owned by the serial_driver gateway node.)

        # Robot geometry (used to convert m/s → wheel r/s)
        #   wheel_radius : radius of each Mecanum wheel (m)
        #   track_width  : left-to-right distance between wheel centres (m)
        #   wheel_base   : front-to-back distance between wheel centres (m)
        # The Mecanum kinematic term uses (l + w) = (wheel_base/2 + track_width/2),
        # i.e. the half-diagonal from the chassis centre to a wheel.
        self.declare_parameter('wheel_radius', 0.0325)   # metres
        self.declare_parameter('track_width', 0.10)       # metres (left-to-right)
        self.declare_parameter('wheel_base', 0.10)        # metres (front-to-back)

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

        port = '(gateway-managed)'
        baudrate = 0
        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.track_width = self.get_parameter('track_width').value
        self.wheel_base = self.get_parameter('wheel_base').value
        self.motor_ids = list(self.get_parameter('motor_ids').value)
        self.invert_motors = list(self.get_parameter('invert_motors').value)
        self.watchdog_timeout = self.get_parameter('watchdog_timeout').value
        self.max_wheel_speed = self.get_parameter('max_wheel_speed').value
        self.emergency_stop_button = self.get_parameter(
            'emergency_stop_button'
        ).value
        log_level = self.get_parameter('log_level').value

        # Pre-compute the kinematic constant used in the Mecanum equations.
        # K = (l + w) where l = wheel_base/2, w = track_width/2.
        # This is the half-diagonal from the chassis centre to each wheel.
        self._kinematic_K = (self.wheel_base + self.track_width) / 2.0

        # Dual ROS2 + developer-friendly file logger
        self.log = NodeLogger(self, level=log_level)

        self.log.info(
            f'MotorDriverNode starting (publishes /motor_cmd).'
        )
        self.log.info(
            f'  wheel_radius={self.wheel_radius} m, '
            f'track_width={self.track_width} m, '
            f'wheel_base={self.wheel_base} m, '
            f'K=(l+w)={self._kinematic_K:.4f} m'
        )
        self.log.info(
            f'  motor_ids={self.motor_ids}, '
            f'invert_motors={self.invert_motors}, '
            f'max_wheel_speed={self.max_wheel_speed} r/s, '
            f'emergency_stop_button={self.emergency_stop_button}'
        )

        # ── ROS2 interface ───────────────────────────────────────────
        # Publisher: per-wheel speeds as JointState. The serial_driver
        # gateway subscribes to /motor_cmd and forwards it to the RRC
        # Lite board. This node never touches the serial port.
        self.motor_cmd_pub = self.create_publisher(
            JointState, '/motor_cmd', 10
        )

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
        Convert a Twist message to per-wheel speeds in r/s using full
        Mecanum inverse kinematics (X-configuration, ABAB roller pattern).

        The three Twist components are combined linearly so the robot can
        execute compound motions — e.g. forward + strafe = 45° diagonal,
        or strafe + turn = curved lateral slide.

        Wheel speed equations (in m/s at the wheel contact point):
            v_FL = v_x - v_y - ω·K
            v_FR = v_x + v_y + ω·K
            v_RL = v_x + v_y - ω·K
            v_RR = v_x - v_y + ω·K

        where:
            v_x = linear.x   (forward, m/s)
            v_y = linear.y    (strafe left, m/s — ROS REP-103: +y = left)
            ω   = angular.z   (turn CCW, rad/s)
            K   = (wheel_base + track_width) / 2  (half-diagonal, m)

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

    # ── Command sending ─────────────────────────────────────────────

    def send_wheel_speeds(self, wheel_speeds):
        """Publish per-wheel speeds on /motor_cmd (JointState)."""
        msg = JointState()
        # stamp + frame_id left empty; serial_driver doesn't use them.
        msg.name = [str(mid) for mid, _ in wheel_speeds]
        msg.velocity = [float(spd) for _, spd in wheel_speeds]
        self.motor_cmd_pub.publish(msg)
        self.log.debug(
            f'/motor_cmd TX: {wheel_speeds}'
        )

    def stop_all_motors(self, repeat: int = 1, flush: bool = False):
        """
        Publish a zero-velocity /motor_cmd to stop all motors.

        The `repeat` and `flush` parameters are retained for API
        compatibility with the watchdog/e-stop paths, but are no-ops
        under the gateway model — the serial_driver forwards whatever
        it receives, and the watchdog's repeated sends are handled by
        the 50 Hz command timer re-publishing zero speeds.
        """
        msg = JointState()
        msg.name = [str(mid) for mid in self.motor_ids]
        msg.velocity = [0.0] * len(self.motor_ids)
        for _ in range(repeat):
            self.motor_cmd_pub.publish(msg)
        self.is_stopped = True
        self.log.debug(f'/motor_cmd stop x{repeat}')

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
        is_moving = (
            abs(msg.linear.x) > 0.001
            or abs(msg.linear.y) > 0.001
            or abs(msg.angular.z) > 0.001
        )
        if was_stopped and is_moving:
            self.log.info(
                f'Received movement command: v_x={msg.linear.x:.2f} m/s, '
                f'v_y={msg.linear.y:.2f} m/s, '
                f'ω={msg.angular.z:.2f} rad/s'
            )
        self.log.debug(
            f'cmd_vel: v_x={msg.linear.x:.3f}, v_y={msg.linear.y:.3f}, '
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
                self.log.warning(
                    'EMERGENCY STOP activated — ignoring /cmd_vel and '
                    'sending repeated stop frames'
                )
                # Zero any remembered velocity so the robot does not jump
                # when e-stop is later cleared.
                self.last_twist = Twist()
                # Immediately blast stop frames to the RRC.
                self.stop_all_motors(repeat=5, flush=True)
            else:
                self.log.warning('Emergency stop cleared — resuming normal control')
                # Start from a safe zero velocity; the next cmd_vel will
                # refresh it before any motion command is sent.
                self.last_twist = Twist()
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
                f'v_x={self.last_twist.linear.x:.2f}, '
                f'v_y={self.last_twist.linear.y:.2f}, '
                f'ω={self.last_twist.angular.z:.2f}'
            )
            if self.is_stopped:
                self.log.debug(heartbeat)
            else:
                self.log.info(heartbeat)

        if elapsed > self.watchdog_timeout:
            if not self.is_stopped:
                self.log.warning(
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
        """Publish a stop command before shutting down."""
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
        resilient_spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
