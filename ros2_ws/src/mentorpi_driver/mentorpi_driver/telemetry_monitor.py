#!/usr/bin/env python3
"""Debug telemetry node — in-place terminal display of the command pipeline.

Subscribes to every topic in the teleop → motor/gimbal chain and renders
them as a single updating screen (cursor repositioning, no scroll).
Useful for diagnosing where a command gets lost between gamepad and actuator.

Topics watched:
    /joy          (sensor_msgs/Joy)         — raw gamepad axes & buttons
    /cmd_vel      (geometry_msgs/Twist)     — vehicle motion command
    /gimbal_vel   (geometry_msgs/Twist)     — gimbal rate command (pan/tilt)
    /motor_cmd    (sensor_msgs/JointState)  — per-motor speeds (r/s)
    /gimbal_cmd   (sensor_msgs/JointState)  — per-servo pulse widths (µs)

A small status flag on each row shows whether the topic has received data
in the last second (● live, ○ stale/never). This makes it obvious when a
producer has stopped publishing (e.g. gamepad asleep, node crashed).
A "Mode & Safety" section replicates the edge-detection logic of
teleop_manager (drive ↔ camera toggle on A) and motor_driver (latched
e-stop toggle on X) so you can see the inferred state without having to
watch the node logs. NOTE: these are inferred from /joy locally — they
will drift if the real nodes use different button indices or logic.
Usage:
    ros2 run mentorpi_driver telemetry_monitor
or alongside the stack:
    ros2 launch mentorpi_driver teleop_camera.launch.py camera:=false
    # in another terminal:
    ros2 run mentorpi_driver telemetry_monitor
"""
import sys
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy, JointState


# ANSI escape codes
CLEAR = '\033[2J'
HOME = '\033[H'
CLEAR_LINE = '\033[K'

BAR_WIDTH = 40


def axis_bar(value: float) -> str:
    """Render a signed value (-1..1) as a centered bar."""
    v = max(-1.0, min(1.0, value))
    half = BAR_WIDTH // 2
    pos = int(round(v * half))
    cells = [' '] * BAR_WIDTH
    cells[half] = '|'
    if pos >= 0:
        for i in range(half + 1, half + 1 + pos):
            if 0 <= i < BAR_WIDTH:
                cells[i] = '█'
    else:
        for i in range(half + pos, half):
            if 0 <= i < BAR_WIDTH:
                cells[i] = '█'
    return f'[{''.join(cells)}]'


def liveness(last_seen: float, now: float) -> str:
    """● if seen in the last second, else ○."""
    return '●' if (now - last_seen) < 1.0 else '○'


class TelemetryMonitorNode(Node):
    def __init__(self):
        super().__init__('telemetry_monitor')

        # Latest snapshot of each topic + last-seen timestamp.
        self._joy: Joy | None = None
        self._joy_t = 0.0
        self._cmd_vel: Twist | None = None
        self._cmd_vel_t = 0.0
        self._gimbal_vel: Twist | None = None
        self._gimbal_vel_t = 0.0
        self._motor_cmd: JointState | None = None
        self._motor_cmd_t = 0.0
        self._gimbal_cmd: JointState | None = None
        self._gimbal_cmd_t = 0.0

        # Inferred mode & safety state (replicated from /joy edge-detection).
        # Defaults match teleop_manager (DRIVE) and motor_driver (e-stop off).
        self._mode = 'DRIVE'   # toggled by A button (btn 0)
        self._estop = False    # toggled by X button (btn 3)
        self._prev_mode_btn = 0
        self._prev_estop_btn = 0
        # Button indices — kept here so they're easy to tweak. Must match
        # teleop_manager_params.yaml / motor_driver defaults.
        self._btn_mode = 0      # A
        self._btn_turbo = 7     # R1
        self._btn_estop = 3     # X
        self._btn_recenter = 14  # R3

        self.create_subscription(Joy, '/joy', self._joy_cb, 10)
        self.create_subscription(Twist, '/cmd_vel', self._cmd_vel_cb, 10)
        self.create_subscription(Twist, '/gimbal_vel', self._gimbal_vel_cb, 10)
        self.create_subscription(JointState, '/motor_cmd', self._motor_cmd_cb, 10)
        self.create_subscription(JointState, '/gimbal_cmd', self._gimbal_cmd_cb, 10)

        # Render at ~15 Hz — fast enough to feel live, easy on the terminal.
        self.create_timer(1.0 / 15.0, self._render)
        self._start = time.monotonic()

    # ── callbacks (just store + timestamp) ──────────────────────────

    def _joy_cb(self, msg: Joy):
        self._joy = msg
        self._joy_t = time.monotonic()
        self._update_mode_and_safety(msg)

    def _update_mode_and_safety(self, msg: Joy) -> None:
        """Replicate teleop_manager + motor_driver edge-detection on /joy.

        This is a LOCAL inference of the state the other nodes hold — it
        will drift if their button indices or toggle logic differ from
        the defaults assumed here.
        """
        b = msg.buttons

        def _edge(idx: int, prev: int) -> tuple[int, bool]:
            if idx < 0 or idx >= len(b):
                return prev, False
            curr = b[idx]
            return curr, bool(curr and not prev)

        # Drive ↔ Camera toggle (A button, rising edge)
        curr_mode_btn, mode_edge = _edge(self._btn_mode, self._prev_mode_btn)
        if mode_edge:
            self._mode = 'CAMERA' if self._mode == 'DRIVE' else 'DRIVE'
        self._prev_mode_btn = curr_mode_btn

        # E-stop toggle (X button, rising edge, latched)
        curr_estop_btn, estop_edge = _edge(self._btn_estop, self._prev_estop_btn)
        if estop_edge:
            self._estop = not self._estop
        self._prev_estop_btn = curr_estop_btn

    def _cmd_vel_cb(self, msg: Twist):
        self._cmd_vel = msg
        self._cmd_vel_t = time.monotonic()

    def _gimbal_vel_cb(self, msg: Twist):
        self._gimbal_vel = msg
        self._gimbal_vel_t = time.monotonic()

    def _motor_cmd_cb(self, msg: JointState):
        self._motor_cmd = msg
        self._motor_cmd_t = time.monotonic()

    def _gimbal_cmd_cb(self, msg: JointState):
        self._gimbal_cmd = msg
        self._gimbal_cmd_t = time.monotonic()

    # ── rendering ───────────────────────────────────────────────────

    def _render(self):
        now = time.monotonic()
        out = [HOME]
        out.append(CLEAR_LINE + '╔══ MentorPi command pipeline telemetry ══╗')
        out.append(CLEAR_LINE + f'  uptime {now - self._start:6.1f}s   '
                                f'(● = live   ○ = stale/never)')
        out.append(CLEAR_LINE + '')

        # ── Mode & Safety (inferred from /joy edge-detection) ───────
        mode_colour = '\033[36m' if self._mode == 'CAMERA' else '\033[32m'
        reset = '\033[0m'
        estop_str = ('\033[31m■ E-STOP ACTIVE\033[0m'
                     if self._estop else '\033[32m□ e-stop clear\033[0m')
        turbo = False
        if self._joy is not None and self._btn_turbo < len(self._joy.buttons):
            turbo = bool(self._joy.buttons[self._btn_turbo])
        turbo_str = f'\033[33m⚡ TURBO\033[0m' if turbo else '  turbo off'
        out.append(CLEAR_LINE + f' MODE: {mode_colour}{self._mode}{reset}   '
                                f'{estop_str}   {turbo_str}')
        out.append(CLEAR_LINE + ' (inferred locally from /joy — '
                                'A=mode  X=e-stop  R1=turbo  R3=recenter)')
        out.append(CLEAR_LINE + '')

        # ── /joy ────────────────────────────────────────────────────
        out.append(CLEAR_LINE + f' /joy          {liveness(self._joy_t, now)}')
        if self._joy is not None:
            names = ['L-Stick H', 'L-Stick V', 'R-Stick H', 'R-Stick V',
                     'L-Trig', 'R-Trig', 'D-Pad H', 'D-Pad V']
            for i, v in enumerate(self._joy.axes):
                name = names[i] if i < len(names) else f'Axis{i}'
                out.append(f'{CLEAR_LINE}   [{i}] {name:11s} {v:+.3f} {axis_bar(v)}')
            btn = self._joy.buttons
            btn_names = ['A', 'B', 'C', 'X', 'Y', 'Z', 'L1', 'R1',
                         'L2', 'R2', 'Sel', 'Start', 'Mode', 'L3', 'R3']
            # Role annotations for the functionally-important buttons.
            roles = {
                self._btn_mode: 'mode',
                self._btn_estop: 'e-stop',
                self._btn_turbo: 'turbo',
                self._btn_recenter: 'recenter',
            }
            cells = []
            for i, b in enumerate(btn):
                name = btn_names[i] if i < len(btn_names) else f'B{i}'
                state = '■' if b else '·'
                role = roles.get(i)
                if role:
                    cells.append(f'{name}:{state}({role})')
                else:
                    cells.append(f'{name}:{state}')
            # wrap into rows of 5
            for rs in range(0, len(cells), 5):
                out.append(CLEAR_LINE + '   ' + '  '.join(cells[rs:rs + 5]))
        else:
            out.append(CLEAR_LINE + '   (no data yet)')
        out.append(CLEAR_LINE + '')

        # ── /cmd_vel ────────────────────────────────────────────────
        out.append(CLEAR_LINE + f' /cmd_vel      {liveness(self._cmd_vel_t, now)}')
        if self._cmd_vel is not None:
            cv = self._cmd_vel
            out.append(f'{CLEAR_LINE}   linear.x  (fwd)   {cv.linear.x:+.3f} '
                       f'{axis_bar(cv.linear.x)}')
            out.append(f'{CLEAR_LINE}   linear.y  (slew)  {cv.linear.y:+.3f} '
                       f'{axis_bar(cv.linear.y)}')
            out.append(f'{CLEAR_LINE}   angular.z (turn)  {cv.angular.z:+.3f} '
                       f'{axis_bar(cv.angular.z / 5.0)}')  # scale for display
        else:
            out.append(CLEAR_LINE + '   (no data yet)')
        out.append(CLEAR_LINE + '')

        # ── /gimbal_vel ─────────────────────────────────────────────
        out.append(CLEAR_LINE + f' /gimbal_vel   {liveness(self._gimbal_vel_t, now)}')
        if self._gimbal_vel is not None:
            gv = self._gimbal_vel
            out.append(f'{CLEAR_LINE}   linear.x  (pan)   {gv.linear.x:+.3f} '
                       f'{axis_bar(gv.linear.x)}')
            out.append(f'{CLEAR_LINE}   linear.y  (tilt)  {gv.linear.y:+.3f} '
                       f'{axis_bar(gv.linear.y)}')
        else:
            out.append(CLEAR_LINE + '   (no data yet)')
        out.append(CLEAR_LINE + '')

        # ── /motor_cmd ──────────────────────────────────────────────
        out.append(CLEAR_LINE + f' /motor_cmd    {liveness(self._motor_cmd_t, now)}')
        if self._motor_cmd is not None and self._motor_cmd.name:
            mc = self._motor_cmd
            for n, v in zip(mc.name, mc.velocity):
                out.append(f'{CLEAR_LINE}   motor {n}  {v:+.3f} r/s  '
                           f'{axis_bar(max(-1.0, min(1.0, v)))}')
        else:
            out.append(CLEAR_LINE + '   (no data yet)')
        out.append(CLEAR_LINE + '')

        # ── /gimbal_cmd ─────────────────────────────────────────────
        out.append(CLEAR_LINE + f' /gimbal_cmd   {liveness(self._gimbal_cmd_t, now)}')
        if self._gimbal_cmd is not None and self._gimbal_cmd.name:
            gc = self._gimbal_cmd
            motion = gc.effort[0] if gc.effort else 0.0
            out.append(f'{CLEAR_LINE}   motion_time = {motion:.0f} ms')
            for n, p in zip(gc.name, gc.position):
                # pulse 500-2500 → -1..1 for the bar
                norm = (p - 1500.0) / 1000.0
                out.append(f'{CLEAR_LINE}   servo {n}  {p:7.0f} µs  '
                           f'{axis_bar(norm)}')
        else:
            out.append(CLEAR_LINE + '   (no data yet)')
        out.append(CLEAR_LINE + '')
        out.append(CLEAR_LINE + ' Ctrl+C to quit.')

        sys.stdout.write('\n'.join(out))
        sys.stdout.flush()


def main(args=None):
    rclpy.init(args=args)
    node = TelemetryMonitorNode()
    sys.stdout.write(CLEAR + HOME)
    sys.stdout.flush()
    try:
        from .logging_utils import resilient_spin
        resilient_spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # leave a clean line
        sys.stdout.write('\n')
        sys.stdout.flush()
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
