# Slice 4: Wireless Game Controller

> Part of the [[Project-Overview]]. Prerequisite: [[Slice-3-Overview]]

## Status: IN PROGRESS (2026-07-14)

## Objective

Replace keyboard teleoperation with a physical USB game controller for fluid manual driving.

## Hardware

- **Controller:** SHANWAN Android Gamepad (USB HID, vendor `2563:0526`)
- **Device node:** `/dev/input/js0` (world-readable, no udev rule needed)
- **8 axes, 15 buttons** — full mapping in [[Progress]] and `/memories/repo/gamepad-mapping.md`

## What's Done

1. **Controller detection** ✓ — `joy_node` reads `/dev/input/js0` and publishes `/joy`
2. **Controller mapping** ✓ — all axes and buttons mapped by hand using `joy_inspector`
3. **`joy_inspector` utility** ✓ — live in-place display of axes (bars) and buttons
4. **`teleop_twist_joy` config** ✓ — YAML config + launch file created

## Control Scheme

| Control | Axis/Button | Action |
|---------|-------------|--------|
| Left stick Y (axis 1) | up/down | Drive forward/back (linear.x, 0.5 m/s) |
| Left stick X (axis 0) | left/right | Turn left/right (angular.z, 2.5 rad/s) |
| Right stick X (axis 2) | left/right | Strafe (linear.y, for mecanum in Slice 5) |
| R1 bumper (7) | hold | Turbo (2× speed) |
| **X button (3)** | press | **Emergency stop** — latches until pressed again |

The left stick is spring-loaded and returns to zero when released, so it acts as a natural deadman. The dedicated A-button deadman has been removed to free the thumb for other controls.

`/joy` (and therefore `/cmd_vel`) is published at a constant **50 Hz** by setting `joy_node`'s `autorepeat_rate` to `50.0`. This prevents the motor driver's watchdog from firing when the stick is held still.

## What's Next

5. **Test & tune** ⬜ — launch the full stack and verify driving
6. **Safety review** ⬜ — confirm deadman + watchdog behaviour

See [[Progress]] for the detailed log.

## Files

- `ros2_ws/src/mentorpi_driver/mentorpi_driver/joy_inspector.py` — live gamepad display
- `ros2_ws/src/mentorpi_driver/config/teleop_joy_params.yaml` — joy→cmd_vel mapping
- `ros2_ws/src/mentorpi_driver/launch/gamepad_teleop.launch.py` — full stack launch

## Prerequisites

- ✅ [[Slice-3-Overview]] complete (motor driver responds to `/cmd_vel`)
