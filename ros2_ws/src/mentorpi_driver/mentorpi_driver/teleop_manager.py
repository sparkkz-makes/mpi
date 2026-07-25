"""
Teleop Manager Node — Slice 6 (Vision & Gimbal Integration)

Replaces teleop_twist_joy. Owns the gamepad → command mapping AND the
drive/camera mode toggle. Publishes three topics:

    /cmd_vel          (geometry_msgs/Twist)  — vehicle motion
    /gimbal_vel       (geometry_msgs/Twist)  — gimbal rate commands
    /gimbal_recenter  (std_msgs/Empty)        — one-shot recenter trigger

Mode behaviour (right stick has two modes):
    Mode 1 (DRIVE, default):
        Left stick  → /cmd_vel.linear.x (fwd)    + /cmd_vel.angular.z (turn)
        Right stick → /cmd_vel.linear.y (slew/strafe)
        /gimbal_vel = zeros (gimbal holds position)
    Mode 2 (CAMERA):
        Left stick  → /cmd_vel.linear.x (fwd)    + /cmd_vel.angular.z (turn)
                      (UNCHANGED — driving continues while aiming the camera)
        Right stick → /gimbal_vel.linear.x (pan rate) + .linear.y (tilt rate)
        /cmd_vel.linear.y = 0  (slew suppressed; no need to stop the robot)

Mode toggle:
    A button (rising edge) → flip mode. No motor stop — slew just goes to
    zero and the right stick is repurposed for the gimbal.

Recenter:
    Right-stick click (R3, rising edge) → publish one Empty on
    /gimbal_recenter. The gimbal_driver snaps both servos to center.

Turbo:
    R1 bumper (button 7) held → use turbo scales (2× drive speed, 2×
    gimbal rate). Same convention as the old teleop_twist_joy config.

This node is transport-agnostic (no serial, no protocol). It only reads
/joy and publishes command topics.

Parameters (see config/teleop_manager_params.yaml):
    Axis indices, scales, button indices, deadzone, publish_rate_hz.

Usage:
    ros2 run mentorpi_driver teleop_manager
"""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy
from std_msgs.msg import Empty

from .logging_utils import NodeLogger, resilient_spin


# Mode constants
MODE_DRIVE = 1
MODE_CAMERA = 2


class TeleopManagerNode(Node):
    """Gamepad → /cmd_vel + /gimbal_vel + /gimbal_recenter, with mode toggle."""

    def __init__(self):
        super().__init__('teleop_manager')

        # ── Parameters: axis indices ─────────────────────────────────
        # SHANWAN Android Gamepad mapping (verified 2026-07-14, see
        # docs/vault/mpi/Slice-4/Progress.md and config/teleop_joy_params.yaml).
        #   0: L-Stick H (left=+1, right=-1)   INVERTED
        #   1: L-Stick V (up=+1, down=-1)
        #   2: R-Stick H (left=+1, right=-1)   INVERTED
        #   3: R-Stick V (up=+1, down=-1)
        self.declare_parameter('axis_linear_x', 1)    # L-stick V → fwd
        self.declare_parameter('axis_angular_z', 0)   # L-stick H → turn
        self.declare_parameter('axis_slew', 2)        # R-stick H → strafe (drive mode)
        self.declare_parameter('axis_pan', 2)         # R-stick H → pan   (camera mode)
        self.declare_parameter('axis_tilt', 3)        # R-stick V → tilt  (camera mode)

        # ── Parameters: scales (normal / turbo) ──────────────────────
        # Drive scales (m/s, rad/s) — match the old teleop_twist_joy config.
        self.declare_parameter('scale_linear_x', 0.5)
        self.declare_parameter('scale_linear_x_turbo', 1.0)
        self.declare_parameter('scale_angular_z', 2.5)
        self.declare_parameter('scale_angular_z_turbo', 5.0)
        self.declare_parameter('scale_slew', 0.5)
        self.declare_parameter('scale_slew_turbo', 1.0)
        # Gimbal scales (dimensionless [-1,1] → published as-is; gimbal_driver
        # multiplies by its own *_max_rate params to get µs/s).
        self.declare_parameter('scale_pan', 1.0)
        self.declare_parameter('scale_pan_turbo', 1.0)
        self.declare_parameter('scale_tilt', 1.0)
        self.declare_parameter('scale_tilt_turbo', 1.0)

        # ── Parameters: buttons ──────────────────────────────────────
        #   0: A   3: X   7: R1   14: R-stick click (R3)
        self.declare_parameter('mode_toggle_button', 0)   # A
        self.declare_parameter('turbo_button', 7)         # R1
        self.declare_parameter('recenter_button', 14)     # R3 (R-stick click)

        # ── Parameters: misc ─────────────────────────────────────────
        self.declare_parameter('deadzone', 0.05)
        self.declare_parameter('publish_rate_hz', 50.0)
        self.declare_parameter('log_level', 'info')

        # ── Load parameters ──────────────────────────────────────────
        self.ax_lin_x = int(self.get_parameter('axis_linear_x').value)
        self.ax_ang_z = int(self.get_parameter('axis_angular_z').value)
        self.ax_slew = int(self.get_parameter('axis_slew').value)
        self.ax_pan = int(self.get_parameter('axis_pan').value)
        self.ax_tilt = int(self.get_parameter('axis_tilt').value)

        self.s_lin_x = float(self.get_parameter('scale_linear_x').value)
        self.s_lin_x_t = float(self.get_parameter('scale_linear_x_turbo').value)
        self.s_ang_z = float(self.get_parameter('scale_angular_z').value)
        self.s_ang_z_t = float(self.get_parameter('scale_angular_z_turbo').value)
        self.s_slew = float(self.get_parameter('scale_slew').value)
        self.s_slew_t = float(self.get_parameter('scale_slew_turbo').value)
        self.s_pan = float(self.get_parameter('scale_pan').value)
        self.s_pan_t = float(self.get_parameter('scale_pan_turbo').value)
        self.s_tilt = float(self.get_parameter('scale_tilt').value)
        self.s_tilt_t = float(self.get_parameter('scale_tilt_turbo').value)

        self.btn_mode = int(self.get_parameter('mode_toggle_button').value)
        self.btn_turbo = int(self.get_parameter('turbo_button').value)
        self.btn_recenter = int(self.get_parameter('recenter_button').value)

        self.deadzone = float(self.get_parameter('deadzone').value)
        pub_rate = float(self.get_parameter('publish_rate_hz').value)
        log_level = self.get_parameter('log_level').value

        self.log = NodeLogger(self, level=log_level)

        # ── State ────────────────────────────────────────────────────
        self.mode = MODE_DRIVE
        self._prev_mode_btn = 0
        self._prev_recenter_btn = 0

        # Latest /joy snapshot (so the timer can publish at a steady rate
        # even between joy messages — matches joy_node autorepeat pattern).
        self.latest_joy = Joy()

        self.log.info(
            f'TeleopManagerNode starting. '
            f'axes: lin_x={self.ax_lin_x}, ang_z={self.ax_ang_z}, '
            f'slew/pan={self.ax_slew}, tilt={self.ax_tilt}. '
            f'buttons: mode(A)={self.btn_mode}, turbo(R1)={self.btn_turbo}, '
            f'recenter(R3)={self.btn_recenter}. '
            f'publish_rate={pub_rate} Hz, mode=DRIVE'
        )

        # ── ROS2 interface ───────────────────────────────────────────
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.gimbal_vel_pub = self.create_publisher(Twist, '/gimbal_vel', 10)
        self.recenter_pub = self.create_publisher(Empty, '/gimbal_recenter', 10)

        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10
        )

        # Steady-rate publisher (matches motor_driver's 50 Hz watchdog
        # expectation — /cmd_vel must keep flowing or motors stop).
        self.create_timer(1.0 / pub_rate, self.publish_callback)

    # ── Helpers ─────────────────────────────────────────────────────

    def _axis(self, joy: Joy, idx: int) -> float:
        """Read an axis value, returning 0.0 if out of range."""
        if idx < 0 or idx >= len(joy.axes):
            return 0.0
        v = joy.axes[idx]
        if abs(v) < self.deadzone:
            return 0.0
        return v

    def _button(self, joy: Joy, idx: int) -> int:
        """Read a button state, returning 0 if out of range."""
        if idx < 0 or idx >= len(joy.buttons):
            return 0
        return joy.buttons[idx]

    def _rising_edge(self, prev: int, curr: int) -> bool:
        return curr and not prev

    # ── Callbacks ───────────────────────────────────────────────────

    def joy_callback(self, msg: Joy) -> None:
        """Store the latest /joy and handle edge-triggered buttons."""
        # Mode toggle (A button, rising edge)
        curr_mode = self._button(msg, self.btn_mode)
        if self._rising_edge(self._prev_mode_btn, curr_mode):
            self.mode = MODE_CAMERA if self.mode == MODE_DRIVE else MODE_DRIVE
            mode_name = 'CAMERA' if self.mode == MODE_CAMERA else 'DRIVE'
            self.log.info(f'Mode toggle → {mode_name}')
        self._prev_mode_btn = curr_mode

        # Recenter (R3, rising edge) — fire-and-forget
        curr_recenter = self._button(msg, self.btn_recenter)
        if self._rising_edge(self._prev_recenter_btn, curr_recenter):
            self.recenter_pub.publish(Empty())
            self.log.info('Recenter triggered (R3 click)')
        self._prev_recenter_btn = curr_recenter

        self.latest_joy = msg

    def publish_callback(self) -> None:
        """Publish /cmd_vel and /gimbal_vel at the steady rate."""
        joy = self.latest_joy
        turbo = bool(self._button(joy, self.btn_turbo))

        # ── Left stick → fwd + turn (same in both modes) ─────────────
        lin_x = self._axis(joy, self.ax_lin_x) * (
            self.s_lin_x_t if turbo else self.s_lin_x
        )
        ang_z = self._axis(joy, self.ax_ang_z) * (
            self.s_ang_z_t if turbo else self.s_ang_z
        )

        # ── Right stick → slew (drive) OR pan/tilt (camera) ──────────
        gimbal_vel = Twist()
        if self.mode == MODE_DRIVE:
            slew = self._axis(joy, self.ax_slew) * (
                self.s_slew_t if turbo else self.s_slew
            )
            cmd_vel = Twist()
            cmd_vel.linear.x = lin_x
            cmd_vel.linear.y = slew
            cmd_vel.angular.z = ang_z
            # gimbal_vel stays zero → gimbal holds position
        else:  # MODE_CAMERA
            cmd_vel = Twist()
            cmd_vel.linear.x = lin_x
            cmd_vel.linear.y = 0.0   # slew suppressed
            cmd_vel.angular.z = ang_z
            pan = self._axis(joy, self.ax_pan) * (
                self.s_pan_t if turbo else self.s_pan
            )
            tilt = self._axis(joy, self.ax_tilt) * (
                self.s_tilt_t if turbo else self.s_tilt
            )
            gimbal_vel.linear.x = pan
            gimbal_vel.linear.y = tilt

        self.cmd_vel_pub.publish(cmd_vel)
        self.gimbal_vel_pub.publish(gimbal_vel)

    # ── Shutdown ────────────────────────────────────────────────────

    def destroy_node(self):
        """Publish a zero /cmd_vel on shutdown so the robot stops."""
        try:
            self.cmd_vel_pub.publish(Twist())
            self.log.info('Published zero /cmd_vel on shutdown.')
        except Exception as e:
            self.log.error(f'Shutdown publish failed: {e}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TeleopManagerNode()
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
