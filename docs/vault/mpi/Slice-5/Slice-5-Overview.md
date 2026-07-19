# Slice 5: Full Mecanum Motion Control

> Part of the [[Project-Overview]]. Prerequisite: [[Slice-4-Overview]]

## Status: COMPLETE (2026-07-19)

## Objective

Implement inverse kinematics to support true omnidirectional movement (forward, lateral strafing, and rotation) using the Mecanum wheel configuration. All three motion components combine linearly so the robot can execute compound motions (e.g. drive forward while slewing, slew + forward = 45° diagonal, slew + turn = curved lateral slide).

## What's Done

1. **Mecanum inverse kinematics** ✓ — replaced the Slice 3 differential-drive model in `motor_driver.py` with the full 4-wheel X-pattern equations.
2. **Strafe axis wired through** ✓ — `linear.y` from `/cmd_vel` now drives the right stick (axis 2) and is consumed by the kinematics (previously ignored).
3. **Strafe sign convention fixed** ✓ — `teleop_joy_params.yaml` updated so stick right → strafe right under REP-103 (`+y` = left).
4. **New `wheel_base` parameter** ✓ — front-to-back wheel distance, needed for the `(l + w)` kinematic term.
5. **Build verified** ✓ — `colcon build` clean.

## Control Scheme

| Control | Input | Action |
|---------|-------|--------|
| Left stick Y (axis 1) | up/down | Drive forward/back (`linear.x`, 0.5 m/s) |
| Left stick X (axis 0) | left/right | Turn left/right (`angular.z`, 2.5 rad/s) |
| Right stick X (axis 2) | left/right | Strafe left/right (`linear.y`, 0.5 m/s) |
| R1 bumper (button 7) | hold | Turbo (2× all scales) |
| X button (button 3) | press | Emergency stop (latched) |

All three motion components are summed, so:
- Forward + strafe right (equal magnitude) → 45° forward-right diagonal
- Strafe + turn → curved lateral slide
- Forward + turn → arc forward while rotating

## Future: Camera Gimbal on Right Stick

The right stick is intentionally kept on a separate axis from the drive stick so it can be **double-tasked** for the 2-DOF camera gimbal in Slice 6. The plan:

- **Default (no trigger):** right stick X → strafe (`linear.y`)
- **Left trigger (L2, button 8) held:** right stick X → camera pan, right stick Y (axis 3) → camera tilt

This will be implemented as a mode switch in a new gimbal node (or in `teleop_twist_joy`'s remapping) — the motor driver itself does not need to change, since it only consumes `/cmd_vel` and the gimbal node will consume a separate `/gimbal_cmd` topic.

## Files Changed

- `ros2_ws/src/mentorpi_driver/mentorpi_driver/motor_driver.py` — Mecanum kinematics + `wheel_base` parameter
- `ros2_ws/src/mentorpi_driver/config/teleop_joy_params.yaml` — strafe scale sign fix + updated comments

## See Also

- [[Mecanum-Kinematics]] — the full math derivation
- [[Progress]] — step-by-step log
- [[Slice-3-Overview]] / [[Differential-Drive-Kinematics]] — the previous model this replaces

## Prerequisites

- ✅ [[Slice-3-Overview]] complete (motor driver responds to `/cmd_vel`)
- ✅ [[Slice-4-Overview]] complete (gamepad → `/cmd_vel` working)
