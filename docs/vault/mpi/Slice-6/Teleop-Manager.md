# Teleop Manager & Combined Launch (Slice 6)

## Status
**teleop_manager node: DONE & verified (11/11 in-process tests pass, 2026-07-25).**
Combined launch file: DONE. **Servo discovery: DONE (2026-07-26)** — gimbal
verified working on hardware with correct axis mapping and sign conventions.

## Debug Telemetry Monitor

A `telemetry_monitor` node was added (2026-07-26) for diagnosing the
command pipeline. It subscribes to every topic in the chain and renders
an in-place terminal display:

- `/joy` — raw axes & buttons (with role annotations: mode/e-stop/turbo/recenter)
- `/cmd_vel` — fwd/slew/turn
- `/gimbal_vel` — pan/tilt rates
- `/motor_cmd` — per-motor speeds (r/s)
- `/gimbal_cmd` — per-servo pulse widths (µs) + motion time

Plus a **Mode & Safety** header showing the inferred drive/camera mode
(A button toggle), e-stop state (X button latch), and turbo (R1).

```bash
ros2 run mentorpi_driver telemetry_monitor
```

Each topic row shows a liveness dot (● live / ○ stale) so it's obvious
when a producer has stopped publishing.

## Overview

`teleop_manager` replaces `teleop_twist_joy`. It owns the gamepad → command
mapping AND the drive/camera mode toggle. It publishes three topics:

- `/cmd_vel` (`geometry_msgs/Twist`) — vehicle motion (fwd/turn/slew)
- `/gimbal_vel` (`geometry_msgs/Twist`) — gimbal rate commands (pan/tilt)
- `/gimbal_recenter` (`std_msgs/Empty`) — one-shot recenter trigger

## Mode Behaviour

The right stick has two modes, toggled by the A button (rising edge):

| Mode | Left stick | Right stick | `/cmd_vel.linear.y` | `/gimbal_vel` |
|------|-----------|-------------|---------------------|---------------|
| DRIVE (default) | fwd + turn | strafe (slew) | from right stick | zeros (hold) |
| CAMERA | fwd + turn (unchanged) | pan + tilt rates | 0 (suppressed) | from right stick |

Key design points:
- **No motor stop on mode toggle** — the left stick keeps driving in both
  modes. Only slew goes to zero in CAMERA mode.
- **A button = rising-edge toggle** — press once to switch, press again
  to switch back. No need to hold.
- **R3 (right-stick click) = recenter** — fires one `Empty` on
  `/gimbal_recenter`; `gimbal_driver` snaps both servos to center.
- **R1 = turbo** — held doubles all scales (drive speed + gimbal rate).
- **X = emergency stop** — still handled by `motor_driver` (latched).

## Files

### `teleop_manager.py` — new node
- Subscribes to `/joy`, publishes `/cmd_vel` + `/gimbal_vel` + `/gimbal_recenter`.
- 50 Hz steady-rate publisher (matches motor_driver's watchdog).
- Edge-triggered button handling (A, R3).
- Deadzone on all axes (default 0.05).
- Transport-agnostic (no serial, no protocol).
- Publishes zero `/cmd_vel` on shutdown.

### `config/teleop_manager_params.yaml` — new
- Axis indices, scales (normal + turbo), button indices, deadzone.
- Defaults match the old `teleop_joy_params.yaml` (Slice 5) for drive scales.

### `launch/teleop_camera.launch.py` — new combined launch
Brings up the full stack:
1. `joy_node` — gamepad → `/joy`
2. `teleop_manager` — `/joy` → `/cmd_vel` + `/gimbal_vel` + `/gimbal_recenter`
3. `serial_driver` — gateway: `/motor_cmd` + `/gimbal_cmd` → serial
4. `motor_driver` — `/cmd_vel` → `/motor_cmd`
5. `gimbal_driver` — `/gimbal_vel` + `/gimbal_recenter` → `/gimbal_cmd`
6. `v4l2_camera` — `/dev/video0` → `/image_raw` (optional, `camera:=false`)
7. `web_video_server` — HTTP MJPG on :8080 (optional)

### `test/test_teleop_manager.py` — new in-process test
11 tests covering both modes, toggle, recenter, and forward driving.
Run with:
```bash
source ros2_ws/activate.sh
cd ros2_ws/src/mentorpi_driver && python3 test/test_teleop_manager.py
```

### `setup.py` / `package.xml`
- Added `teleop_manager` entry point.
- Registered `teleop_manager_params.yaml` and `teleop_camera.launch.py`.

## Verification (2026-07-25)

All 11 in-process tests pass:
```
=== SUMMARY: 11/11 passed ===
  PASS: DRIVE: cmd_vel.linear.y == -0.5 (strafe right)
  PASS: DRIVE: gimbal_vel.linear.x == 0.0
  PASS: DRIVE: gimbal_vel.linear.y == 0.0
  PASS: Mode toggled to CAMERA (tm.mode == 2)
  PASS: CAMERA: cmd_vel.linear.y == 0.0 (slew suppressed)
  PASS: CAMERA: gimbal_vel.linear.x == -1.0 (pan)
  PASS: CAMERA: gimbal_vel.linear.y == 0.0 (no tilt)
  PASS: CAMERA tilt: gimbal_vel.linear.y == 1.0
  PASS: Recenter published (recenter_count >= 1)
  PASS: Mode toggled back to DRIVE (tm.mode == 1)
  PASS: DRIVE fwd: cmd_vel.linear.x == 0.5
```

## Running

The `stu` user is now in all required groups (`input`, `dialout`, `video`),
so the stack launches directly without any wrapper scripts:

```bash
# Full stack (teleop + camera + gimbal)
ros2 launch mentorpi_driver teleop_camera.launch.py

# Teleop + gimbal only (no camera)
ros2 launch mentorpi_driver teleop_camera.launch.py camera:=false

# Debug telemetry monitor (in another terminal)
ros2 run mentorpi_driver telemetry_monitor
```

**Important — permissions:** The `stu` user must be in the `input`,
`dialout`, and `video` groups. All three produce **silent failures** if
missing (the node runs but never opens the device, and logs nothing):
- `input` — joy_node opens `/dev/input/js0` with O_RDWR (haptic/rumble)
- `dialout` — serial_driver opens `/dev/ttyACM0`
- `video` — v4l2_camera opens `/dev/video0`

Fix once: `sudo usermod -aG input,dialout,video stu`, then **re-login**.
All three groups have been added (2026-07-26); no wrapper script needed.

## Topic Graph

```
joy_node ──/joy──────────────────▶ teleop_manager ──/cmd_vel──────────▶ motor_driver ──/motor_cmd───┐
                                  │                ──/gimbal_vel──────▶ gimbal_driver ──/gimbal_cmd──┤──▶ serial_driver ──▶ /dev/ttyACM0
                                  │                ──/gimbal_recenter─▶ gimbal_driver               │
                                  │                                                                │
v4l2_camera ──/image_raw──────────┤                                                                │
              ──/image_raw/compressed──▶ web_video_server ──HTTP :8080──▶ browser (phone/PC)       │
                                                                                                    │
(legacy) /test_led ────────────────────────────────────────────────────────────────────────────────┘
```

## Servo Discovery (DONE — 2026-07-26)

Physical test confirmed the gimbal configuration. The verified values
live in `config/teleop_manager_params.yaml` (axis/scale) and
`config/gimbal_params.yaml` (servo IDs/pulses):

| Setting | Value | Notes |
|---------|-------|-------|
| `pan_servo_id` | 1 | RRC Lite servo ID 1 = pan (yaw) |
| `tilt_servo_id` | 2 | RRC Lite servo ID 2 = tilt (pitch) |
| `axis_pan` | 3 | R-stick V → pan rate |
| `axis_tilt` | 2 | R-stick H → tilt rate |
| `scale_pan` | -1.0 | negated (push right → pan right) |
| `scale_tilt` | 1.0 | positive (push up → tilt up) |

The original guess had `axis_pan: 2` / `axis_tilt: 3`, but physical
testing showed the stick axes were swapped relative to the servos.

## Next Steps

1. **Camera calibration** — generate a camera_info YAML for `/image_raw`
   (needed for CV/AI later; not needed for streaming).
2. **Migrate buzzer_node** to the gateway pattern (low priority).
