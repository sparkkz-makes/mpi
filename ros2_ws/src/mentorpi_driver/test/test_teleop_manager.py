#!/usr/bin/env python3
"""In-process test for teleop_manager mode logic.

Uses separate publisher/subscriber nodes in a single-threaded executor
so message delivery is reliable. Verifies:
  - DRIVE mode: right stick → /cmd_vel.linear.y (slew), /gimbal_vel = 0
  - CAMERA mode: right stick → /gimbal_vel (pan/tilt), /cmd_vel.linear.y = 0
  - A button toggles mode (rising edge)
  - R3 click → /gimbal_recenter
"""
import sys
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy
from std_msgs.msg import Empty

from mentorpi_driver.teleop_manager import TeleopManagerNode


class JoyPub(Node):
    def __init__(self):
        super().__init__('joy_pub_test')
        self.pub = self.create_publisher(Joy, '/joy', 10)

    def send(self, axes, buttons):
        msg = Joy()
        msg.axes = [float(a) for a in axes]
        msg.buttons = [int(b) for b in buttons]
        self.pub.publish(msg)


class CmdCapture(Node):
    """Captures /cmd_vel, /gimbal_vel, /gimbal_recenter."""
    def __init__(self):
        super().__init__('cmd_capture_test')
        self.last_cmd_vel = Twist()
        self.last_gimbal_vel = Twist()
        self.recenter_count = 0
        self.cmd_count = 0
        self.gimbal_count = 0
        self.create_subscription(Twist, '/cmd_vel', self._on_cmd, 10)
        self.create_subscription(Twist, '/gimbal_vel', self._on_gimbal, 10)
        self.create_subscription(Empty, '/gimbal_recenter', self._on_recenter, 10)

    def _on_cmd(self, m):
        self.last_cmd_vel = m
        self.cmd_count += 1

    def _on_gimbal(self, m):
        self.last_gimbal_vel = m
        self.gimbal_count += 1

    def _on_recenter(self, m):
        self.recenter_count += 1


def approx(a, b, tol=0.01):
    return abs(a - b) < tol


def main():
    rclpy.init()
    tm = TeleopManagerNode()
    jp = JoyPub()
    cap = CmdCapture()
    exe = SingleThreadedExecutor()
    exe.add_node(tm)
    exe.add_node(jp)
    exe.add_node(cap)

    def spin_for(seconds):
        end = time.time() + seconds
        while time.time() < end:
            exe.spin_once(timeout_sec=0.02)

    def pump_joy(axes, buttons, seconds=0.5):
        """Publish joy continuously and spin so callbacks fire."""
        end = time.time() + seconds
        while time.time() < end:
            jp.send(axes, buttons)
            exe.spin_once(timeout_sec=0.02)

    results = []
    def check(name, cond):
        results.append((name, cond))
        print(f"  {'PASS' if cond else 'FAIL'}: {name}")

    AXES_NEUTRAL = [0.0] * 8
    BTNS_NEUTRAL = [0] * 15

    # ── Warmup: flush any stale joy messages and reset button state ─
    pump_joy(AXES_NEUTRAL, BTNS_NEUTRAL, 0.3)

    # ── Test 1: DRIVE mode, right stick right (axis 2 = -1.0) ──────
    print("\n=== Test 1: DRIVE mode, right stick right ===")
    pump_joy([0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0], BTNS_NEUTRAL, 0.5)
    cv, gv = cap.last_cmd_vel, cap.last_gimbal_vel
    print(f"  cmd_vel:  x={cv.linear.x:.3f}, y={cv.linear.y:.3f}, z={cv.angular.z:.3f}")
    print(f"  gimbal_vel: x={gv.linear.x:.3f}, y={gv.linear.y:.3f}")
    print(f"  counts: cmd={cap.cmd_count}, gimbal={cap.gimbal_count}")
    check("DRIVE: cmd_vel.linear.y == -0.5 (strafe right)", approx(cv.linear.y, -0.5))
    check("DRIVE: gimbal_vel.linear.x == 0.0", approx(gv.linear.x, 0.0))
    check("DRIVE: gimbal_vel.linear.y == 0.0", approx(gv.linear.y, 0.0))

    # ── Test 2: Toggle to CAMERA mode (A rising edge) ──────────────
    print("\n=== Test 2: Toggle to CAMERA mode (A press) ===")
    # Send one A=1 message (rising edge), then neutral
    bt = list(BTNS_NEUTRAL); bt[0] = 1
    jp.send(AXES_NEUTRAL, bt)
    spin_for(0.1)
    jp.send(AXES_NEUTRAL, BTNS_NEUTRAL)
    spin_for(0.1)
    check("Mode toggled to CAMERA (tm.mode == 2)", tm.mode == 2)

    # ── Test 3: CAMERA mode, right stick right → gimbal pan ────────
    print("\n=== Test 3: CAMERA mode, right stick right ===")
    pump_joy([0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0], BTNS_NEUTRAL, 0.5)
    cv, gv = cap.last_cmd_vel, cap.last_gimbal_vel
    print(f"  cmd_vel:  x={cv.linear.x:.3f}, y={cv.linear.y:.3f}, z={cv.angular.z:.3f}")
    print(f"  gimbal_vel: x={gv.linear.x:.3f}, y={gv.linear.y:.3f}")
    check("CAMERA: cmd_vel.linear.y == 0.0 (slew suppressed)", approx(cv.linear.y, 0.0))
    check("CAMERA: gimbal_vel.linear.x == -1.0 (pan)", approx(gv.linear.x, -1.0))
    check("CAMERA: gimbal_vel.linear.y == 0.0 (no tilt)", approx(gv.linear.y, 0.0))

    # ── Test 4: CAMERA mode, right stick up (axis 3 = +1.0) → tilt ─
    print("\n=== Test 4: CAMERA mode, right stick up (tilt) ===")
    pump_joy([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], BTNS_NEUTRAL, 0.5)
    gv = cap.last_gimbal_vel
    print(f"  gimbal_vel: x={gv.linear.x:.3f}, y={gv.linear.y:.3f}")
    check("CAMERA tilt: gimbal_vel.linear.y == 1.0", approx(gv.linear.y, 1.0))

    # ── Test 5: Recenter (R3 click, button 14) ─────────────────────
    print("\n=== Test 5: Recenter trigger (R3 click) ===")
    bt = list(BTNS_NEUTRAL); bt[14] = 1
    jp.send(AXES_NEUTRAL, bt)
    spin_for(0.1)
    jp.send(AXES_NEUTRAL, BTNS_NEUTRAL)
    spin_for(0.1)
    check("Recenter published (recenter_count >= 1)", cap.recenter_count >= 1)
    print(f"  recenter_count = {cap.recenter_count}")

    # ── Test 6: Toggle back to DRIVE mode ──────────────────────────
    print("\n=== Test 6: Toggle back to DRIVE mode ===")
    bt = list(BTNS_NEUTRAL); bt[0] = 1
    jp.send(AXES_NEUTRAL, bt)
    spin_for(0.1)
    jp.send(AXES_NEUTRAL, BTNS_NEUTRAL)
    spin_for(0.1)
    check("Mode toggled back to DRIVE (tm.mode == 1)", tm.mode == 1)

    # ── Test 7: DRIVE mode again, left stick fwd (axis 1 = +1.0) ───
    print("\n=== Test 7: DRIVE mode, left stick forward ===")
    pump_joy([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], BTNS_NEUTRAL, 0.5)
    cv = cap.last_cmd_vel
    print(f"  cmd_vel:  x={cv.linear.x:.3f}, y={cv.linear.y:.3f}, z={cv.angular.z:.3f}")
    check("DRIVE fwd: cmd_vel.linear.x == 0.5", approx(cv.linear.x, 0.5))

    # ── Summary ────────────────────────────────────────────────────
    passed = sum(1 for _, c in results if c)
    total = len(results)
    print(f"\n=== SUMMARY: {passed}/{total} passed ===")
    for name, c in results:
        if not c:
            print(f"  FAILED: {name}")

    tm.destroy_node(); jp.destroy_node(); cap.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
