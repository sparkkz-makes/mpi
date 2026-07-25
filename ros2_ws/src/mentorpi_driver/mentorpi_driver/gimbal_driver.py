"""
Gimbal Driver Node — Slice 6 (Vision & Gimbal Integration)

Rate-control integrator for the pan/tilt servos on the RRC Lite board.

This node is transport-agnostic: it does NOT open the serial port. It
publishes /gimbal_cmd (sensor_msgs/JointState) with servo IDs and target
pulse widths; the serial_driver gateway forwards it to the RRC Lite.

Inputs:
    /gimbal_vel    (geometry_msgs/Twist)
        linear.x = pan rate  (signed; sign = direction)
        linear.y = tilt rate (signed)
        Units are dimensionless [-1, 1] from the joystick; scaled by
        the pan_max_rate / tilt_max_rate parameters (µs per second).
    /gimbal_recenter (std_msgs/Empty)
        One-shot: snap both servos to their center pulse, with a smooth
        motion_time (default 300 ms).

Output:
    /gimbal_cmd (sensor_msgs/JointState)
        name     = [pan_id, tilt_id] (as strings)
        position = [pan_pulse_us, tilt_pulse_us]
        effort   = [motion_time_ms]  (applies to all servos in the msg)

Rate-control behaviour:
    - Stick deflection sets the *rate* of servo rotation, not the
      absolute angle. The integrator accumulates pulse width over time.
    - Release the stick (rate → 0): the servo HOLDS its last position.
    - Stick click (handled by teleop_manager → /gimbal_recenter):
      snaps both servos back to center.

Parameters (see config/gimbal_params.yaml):
    pan_servo_id, tilt_servo_id       — RRC servo IDs (1-4)
    pan_center_pulse, tilt_center_pulse — center pulse width (µs, ~1500)
    pan_min_pulse, pan_max_pulse      — travel limits (µs)
    tilt_min_pulse, tilt_max_pulse    — travel limits (µs)
    pan_max_rate                      — max pan rate (µs/s) at full stick
    tilt_max_rate                     — max tilt rate (µs/s) at full stick
    deadzone                          — stick deadzone (abs value below
                                        which rate is zeroed)
    motion_time_ms                    — servo motion time for steady-state
                                        ticks (default 20 = smooth tracking)
    recenter_motion_ms                — motion time for the recenter snap
    tick_rate_hz                      — integrator update rate (default 50)

Usage:
    ros2 run mentorpi_driver gimbal_driver
"""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty

from .logging_utils import NodeLogger, resilient_spin


class GimbalDriverNode(Node):
    """Rate-control integrator for pan/tilt servos."""

    def __init__(self):
        super().__init__('gimbal_driver')

        # ── Parameters ───────────────────────────────────────────────
        # Servo IDs on the RRC Lite (1-indexed, per protocol doc).
        # NOTE: these need physical verification — see
        # docs/vault/mpi/Slice-6/Gimbal-Servo-Discovery.md (to be created).
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
        # 1000 µs/s ≈ 120°/s — a comfortable teleop pan speed.
        self.declare_parameter('pan_max_rate', 1000.0)
        self.declare_parameter('tilt_max_rate', 1000.0)

        # Stick deadzone: |stick| < deadzone → rate = 0 (hold position).
        self.declare_parameter('deadzone', 0.05)

        # Servo motion time (ms) for steady-state tracking ticks.
        # ~ the tick period keeps motion smooth and immediate.
        self.declare_parameter('motion_time_ms', 20)
        # Longer motion time for the recenter snap (visible sweep back).
        self.declare_parameter('recenter_motion_ms', 300)

        # Integrator tick rate (Hz). Should match motor_driver's 50 Hz
        # so gimbal and motor commands interleave cleanly through the
        # serial gateway.
        self.declare_parameter('tick_rate_hz', 50.0)

        self.declare_parameter('log_level', 'info')

        # ── Load parameters ─────────────────────────────────────────
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
        tick_rate = float(self.get_parameter('tick_rate_hz').value)
        log_level = self.get_parameter('log_level').value

        self.log = NodeLogger(self, level=log_level)

        # ── Integrator state ────────────────────────────────────────
        # Start at center so the gimbal is in a known position on boot.
        self.pan_pulse = self.pan_center
        self.tilt_pulse = self.tilt_center
        self._dt = 1.0 / tick_rate

        # Latest rate commands from /gimbal_vel (default: zero = hold).
        self.pan_rate = 0.0
        self.tilt_rate = 0.0

        self.log.info(
            f'GimbalDriverNode starting (publishes /gimbal_cmd). '
            f'pan_id={self.pan_id}, tilt_id={self.tilt_id}, '
            f'pan=[{self.pan_min}-{self.pan_max}]µs '
            f'(center {self.pan_center}), '
            f'tilt=[{self.tilt_min}-{self.tilt_max}]µs '
            f'(center {self.tilt_center}), '
            f'rates={self.pan_max_rate}/{self.tilt_max_rate} µs/s, '
            f'tick={tick_rate} Hz'
        )

        # ── ROS2 interface ───────────────────────────────────────────
        self.gimbal_cmd_pub = self.create_publisher(
            JointState, '/gimbal_cmd', 10
        )
        self.gimbal_vel_sub = self.create_subscription(
            Twist, '/gimbal_vel', self.gimbal_vel_callback, 10
        )
        self.recenter_sub = self.create_subscription(
            Empty, '/gimbal_recenter', self.recenter_callback, 10
        )

        # Send an initial recenter so the gimbal moves to a known
        # position on startup (also confirms the serial path works).
        self.recenter_callback(Empty())

        # Fixed-rate integrator tick.
        self.create_timer(self._dt, self.tick)

    # ── Helpers ─────────────────────────────────────────────────────

    def _apply_deadzone(self, value: float) -> float:
        """Zero out small stick deflections within the deadzone."""
        if abs(value) < self.deadzone:
            return 0.0
        return value

    def _clamp(self, value: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, value))

    def _publish(self, motion_time_ms: int) -> None:
        """Publish current pan/tilt pulse widths on /gimbal_cmd."""
        msg = JointState()
        msg.name = [str(self.pan_id), str(self.tilt_id)]
        msg.position = [float(self.pan_pulse), float(self.tilt_pulse)]
        msg.effort = [float(motion_time_ms)]
        self.gimbal_cmd_pub.publish(msg)

    # ── Callbacks ───────────────────────────────────────────────────

    def gimbal_vel_callback(self, msg: Twist) -> None:
        """
        /gimbal_vel → store the latest rate commands.
        linear.x = pan rate ([-1,1]), linear.y = tilt rate ([-1,1]).
        """
        self.pan_rate = self._apply_deadzone(msg.linear.x)
        self.tilt_rate = self._apply_deadzone(msg.linear.y)
        self.log.debug(
            f'gimbal_vel: pan_rate={self.pan_rate:.3f}, '
            f'tilt_rate={self.tilt_rate:.3f}'
        )

    def recenter_callback(self, msg) -> None:
        """Snap both servos to center with a smooth motion time."""
        self.pan_pulse = self.pan_center
        self.tilt_pulse = self.tilt_center
        self._publish(self.recenter_motion_ms)
        self.log.info(
            f'Recenter: pan→{self.pan_center}µs, tilt→{self.tilt_center}µs '
            f'(motion {self.recenter_motion_ms} ms)'
        )

    def tick(self) -> None:
        """
        Integrator step: advance pulse widths by rate*dt, clamp, publish.
        """
        # Accumulate: Δpulse = rate * max_rate * dt
        self.pan_pulse = self._clamp(
            int(self.pan_pulse + self.pan_rate * self.pan_max_rate * self._dt),
            self.pan_min, self.pan_max,
        )
        self.tilt_pulse = self._clamp(
            int(self.tilt_pulse + self.tilt_rate * self.tilt_max_rate * self._dt),
            self.tilt_min, self.tilt_max,
        )
        self._publish(self.motion_time_ms)

    # ── Shutdown ────────────────────────────────────────────────────

    def destroy_node(self):
        """Recenter on shutdown so the gimbal parks safely."""
        try:
            self.recenter_callback(Empty())
            self.log.info('Gimbal recentered on shutdown.')
        except Exception as e:
            self.log.error(f'Shutdown recenter failed: {e}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GimbalDriverNode()
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
