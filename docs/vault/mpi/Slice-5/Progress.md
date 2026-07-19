# Slice 5: Full Mecanum Motion Control — Progress Log

## Status: COMPLETE (2026-07-19)

## What Was Done

### 1. Replaced Differential-Drive Kinematics with Mecanum IK ✓

The Slice 3 `twist_to_wheel_speeds()` in `motor_driver.py` used a 2-wheel differential-drive model: left side got one speed, right side got another, and `linear.y` (strafe) was silently ignored.

Replaced with the full 4-wheel Mecanum inverse kinematics for an X-pattern (ABAB) layout:

```
v_FL = v_x - v_y - ω·K
v_FR = v_x + v_y + ω·K
v_RL = v_x + v_y - ω·K
v_RR = v_x - v_y + ω·K
```

where `K = (wheel_base + track_width) / 2` is the half-diagonal from chassis centre to wheel.

The three Twist components sum linearly, so compound motions (forward + strafe = diagonal, strafe + turn = curved slide) work for free.

### 2. Added `wheel_base` Parameter ✓

New ROS2 parameter `wheel_base` (default 0.10 m) for the front-to-back wheel centre distance. The kinematic constant `K = (L + W) / 2` is pre-computed in `__init__` as `self._kinematic_K` to avoid re-computing every tick.

### 3. Fixed Strafe Sign in `teleop_joy_params.yaml` ✓

The old config had `scale_linear.y: -0.5` with a comment saying "negate so right = strafe right". Under ROS REP-103 (`+y` = left), this was actually backwards:

- Stick right → axis 2 value = -1.0
- Old: `-1.0 × -0.5 = +0.5` → `linear.y = +0.5` → strafe **left** ❌
- New: `-1.0 × +0.5 = -0.5` → `linear.y = -0.5` → strafe **right** ✅

Changed `scale_linear.y` from `-0.5` to `+0.5` (and turbo from `-1.0` to `+1.0`). Added a clear comment explaining the REP-103 sign convention.

### 4. Updated Logging ✓

- `cmd_vel_callback` now logs `v_y` in both the transition message and debug line.
- Heartbeat now includes `v_y` alongside `v_x` and `ω`.
- `is_moving` check now considers all three components (was only `linear.x` + `angular.z`).

### 5. Documentation ✓

- Updated [[Slice-5-Overview]] from placeholder to complete.
- Created [[Mecanum-Kinematics]] with full derivation and worked examples.

## Files Changed

| File | Change |
|------|--------|
| `ros2_ws/src/mentorpi_driver/mentorpi_driver/motor_driver.py` | Mecanum IK, `wheel_base` param, `v_y` logging |
| `ros2_ws/src/mentorpi_driver/config/teleop_joy_params.yaml` | Strafe scale sign fix, updated comments |
| `docs/vault/mpi/Slice-5/Slice-5-Overview.md` | Filled in (was placeholder) |
| `docs/vault/mpi/Slice-5/Mecanum-Kinematics.md` | New — full math derivation |

## Build & Test

- `colcon build` — clean, 1 package, 2.18s.
- Pylance reports pre-existing type warnings about `get_parameter().value` returning `Unknown | None` (a known ROS2 + static-analysis limitation, not introduced by this slice).

### Hardware Test (to do on the robot)

1. `ros2 launch mentorpi_driver gamepad_teleop.launch.py`
2. **Forward/back:** left stick up/down → robot drives straight (unchanged from Slice 4).
3. **Turn:** left stick left/right → robot turns in place (unchanged).
4. **Strafe:** right stick left/right → robot slides sideways (NEW).
   - Verify direction: stick right → robot moves right.
5. **Diagonal:** left stick up + right stick right → robot moves forward-right at 45°.
6. **Compound:** left stick up + left stick left → robot arcs forward while turning.
7. **Turbo:** hold R1 → all motions 2× faster.
8. **E-stop:** press X → motors stop; press X again → resume.
9. **Watchdog:** release sticks → motors stop within 0.5 s.

If strafe direction is reversed on the real robot, the most likely cause is the Mecanum wheels being installed in an O-pattern instead of X-pattern, or the roller angle assumption being flipped. Fix by negating `scale_linear.y` in the YAML — do **not** change the kinematic equations, which follow the standard convention.

## Future: Camera Gimbal Double-Tasking

The right stick is kept separate from the drive stick so it can be double-tasked for the 2-DOF camera gimbal in Slice 6:

- **Default:** right stick X → strafe (`linear.y` on `/cmd_vel`)
- **L2 trigger held (button 8):** right stick X → camera pan, right stick Y (axis 3) → camera tilt

Implementation plan for Slice 6:
- Add a gimbal node that subscribes to `/joy` and publishes `/gimbal_cmd` (a `JointState` or custom message) when L2 is held.
- When L2 is held, suppress the strafe axis in `teleop_twist_joy` (or run a custom teleop node that gates the strafe output on `!L2`).
- The motor driver does not need to change — it only sees `/cmd_vel`.

## Lessons Learned

1. **REP-103 sign conventions matter.** The old strafe scale was "negated to make right = right" but actually produced left strafe because REP-103 defines `+y` = left. Always trace the sign through the full chain: stick → axis value → scale → Twist field → kinematic equation → wheel direction.

2. **Pre-compute kinematic constants.** `K = (L + W) / 2` doesn't change, so computing it once in `__init__` saves a multiply-add every 50 Hz tick. Minor, but cleaner.

3. **Keep the standard-form equations.** The kinematic equations are written in the standard robot frame (positive `v_y` = strafe left) and the motor inversion is applied **after**. This keeps the math readable and matches textbook references, even though the physical motor wiring is non-standard.
