# Serial Gateway Architecture & Gimbal Driver

## Status
**Gateway refactor: DONE & verified (2026-07-25).** Gimbal driver node: DONE &
**verified on hardware (2026-07-26)** — servo IDs, pulse ranges, and axis
mapping all confirmed. See "Servo discovery" below for the verified values.

## Overview

Refactored the serial communication so that a single `serial_driver` node
owns the RRC Lite UART and acts as a gateway. All actuator nodes
(`motor_driver`, `gimbal_driver`, future nodes) are transport-agnostic:
they publish high-level command topics, and the gateway translates them
into RRC Lite protocol frames.

This means swapping the controller board for a different one would only
require changing `serial_driver` — the high-level logic stays the same.

## Architecture

```
teleop_manager ──/cmd_vel───────────▶ motor_driver ──/motor_cmd───┐
              ──/gimbal_vel─────────▶ gimbal_driver ──/gimbal_cmd──┤──▶ serial_driver ──▶ /dev/ttyACM0
              ──/gimbal_recenter────▶ gimbal_driver                │
                                                                    │
(legacy) /test_led ────────────────────────────────────────────────┘
```

### Topic interface (all `sensor_msgs/JointState`)

| Topic | Producer | Consumer | Fields used |
|---|---|---|---|
| `/motor_cmd` | `motor_driver` | `serial_driver` | `name`=[motor_id], `velocity`=[r/s] |
| `/gimbal_cmd` | `gimbal_driver` | `serial_driver` | `name`=[servo_id], `position`=[pulse µs], `effort`=[motion_ms] |
| `/gimbal_vel` | (future `teleop_manager`) | `gimbal_driver` | `Twist`: linear.x=pan rate, linear.y=tilt rate |
| `/gimbal_recenter` | (future `teleop_manager`) | `gimbal_driver` | `Empty`: snap to center |
| `/test_led` | CLI (legacy) | `serial_driver` | `String`: blink LED 1 |

### Why `JointState` (not a custom message)

- Standard message, no `.msg` file / no rebuild.
- Self-describing: `name` + `position`/`velocity` is exactly "named
  actuators + their setpoints."
- Plottable in `rqt` / Foxglove out of the box.
- The `effort` field is reused for `motion_time_ms` on gimbal commands
  (documented in the serial_driver docstring).

## Files Changed

### `serial_driver.py` — rewritten as the gateway
- Owns `/dev/ttyACM0` exclusively (the only node that imports `serial`).
- Subscribes to `/motor_cmd` and `/gimbal_cmd`, builds frames via
  `RRCLiteProtocol`, writes to serial.
- Retains the legacy `/test_led` channel for Slice 1 proof-of-life.
- Sends a motor stop on shutdown.
- Concurrency: default single-threaded executor serializes callbacks,
  so `serial_conn.write()` calls don't interleave. No lock needed.

### `motor_driver.py` — refactored to publish-only
- Removed `serial` and `RRCLiteProtocol` imports.
- Removed the `serial.Serial(...)` connection block and `port`/`baudrate`
  parameters.
- `send_wheel_speeds()` now publishes `/motor_cmd` (JointState) instead
  of writing serial.
- `stop_all_motors()` publishes a zero-velocity `/motor_cmd`.
- Watchdog and e-stop logic unchanged (still in motor_driver, where it
  belongs — the gateway stays dumb).
- `destroy_node()` publishes a stop before shutdown.

### `gimbal_driver.py` — new node
- Rate-control integrator for pan/tilt servos.
- Subscribes to `/gimbal_vel` (Twist) and `/gimbal_recenter` (Empty).
- Publishes `/gimbal_cmd` (JointState) at 50 Hz.
- Integrator: `pan_pulse += pan_rate * pan_max_rate * dt`, clamped to
  `[pan_min, pan_max]`.
- Release stick → rate = 0 → servo HOLDS last position.
- `/gimbal_recenter` → snap to center with `motion_time_ms=300`.
- Recenters on boot and on shutdown.
- No serial, no protocol — pure logic, fully testable in isolation.

### `config/gimbal_params.yaml` — new
- Servo IDs, pulse ranges, rates, deadzone, motion times.
- **VERIFIED (2026-07-26):** servo ID 1 = pan, ID 2 = tilt, pulse range
  1000-2000 µs (center 1500) all confirmed correct on the hardware.

### `setup.py` / `package.xml`
- Added `gimbal_driver` entry point.
- Registered `gimbal_params.yaml` in `data_files`.
- No new package.xml deps (`sensor_msgs`, `std_msgs`, `geometry_msgs`
  already declared).

## Verification (2026-07-25)

Ran `serial_driver` (debug) + `motor_driver` + `gimbal_driver`, published
a sustained `/cmd_vel` (linear.x=0.1). Confirmed:

1. **Serial port opens:** `Serial port /dev/ttyACM0 opened @ 1000000 baud. Gateway ready.`
2. **`/motor_cmd` published by motor_driver:**
   ```
   name: ['0', '2', '1', '3']
   velocity: [...]   # 4 wheel speeds in r/s
   ```
3. **`/gimbal_cmd` published by gimbal_driver:**
   ```
   name: ['1', '2']
   position: [1500.0, 1500.0]   # centered
   effort: [20.0]               # motion_time_ms
   ```
4. **Frames written to serial at 50 Hz** (serial_driver debug log):
   ```
   TX motor(4): aa550316010400f2bafabe02f2bafa3e01f2bafabe03f2bafabe04
   ```
   Decoded: `aa55` header, `03` FUNC_MOTOR, `16` len, `01` multi-cmd,
   `04` count, then 4× (motor_id + float speed). Valid RRC Lite frame.

## Permissions (important)

The `stu` user was NOT in the `dialout` group → `serial_driver` failed
with `Permission denied: '/dev/ttyACM0'`. Fixed with:
```bash
sudo usermod -aG dialout stu
```
Needs a **new login session** to take effect. Workaround in an existing
shell: `sg dialout -c "..."`.

(Same class of issue as the `video` group for the camera — see
`docs/vault/mpi/Slice-6/Camera-Streaming.md`.)

## Running

The `stu` user is now in all required groups (`input`, `dialout`, `video`),
so the stack launches directly without any `sg` wrappers:

```bash
# Full stack (teleop + camera + gimbal)
ros2 launch mentorpi_driver teleop_camera.launch.py

# Teleop + gimbal only (no camera)
ros2 launch mentorpi_driver teleop_camera.launch.py camera:=false

# Debug telemetry monitor (in another terminal)
ros2 run mentorpi_driver telemetry_monitor
```

For manual testing of individual nodes, see the launch file for the
full node list. The old multi-terminal `sg dialout -c "..."` wrappers
are no longer needed.

## Servo Discovery (DONE — 2026-07-26)

Physical test confirmed the following configuration (all in
`config/teleop_manager_params.yaml` and `config/gimbal_params.yaml`):

| Setting | Value | Notes |
|---------|-------|-------|
| `pan_servo_id` | 1 | RRC Lite servo ID 1 = pan (yaw) |
| `tilt_servo_id` | 2 | RRC Lite servo ID 2 = tilt (pitch) |
| `pan_min/max_pulse` | 1000-2000 µs | center 1500 |
| `tilt_min/max_pulse` | 1000-2000 µs | center 1500 |
| `axis_pan` | 3 | R-stick V → pan rate |
| `axis_tilt` | 2 | R-stick H → tilt rate |
| `scale_pan` | -1.0 | negated (push right → pan right) |
| `scale_tilt` | 1.0 | positive (push up → tilt up) |

**Note on axis swap:** the original guess had `axis_pan: 2` (R-stick H)
and `axis_tilt: 3` (R-stick V), but physical testing showed the stick
axes were swapped relative to the servos. Swapping them fixed it.

## Bugs Found & Fixed (2026-07-26)

### 1. Missing subcommand byte in `cmd_pwm_servo_several`

`RRCLiteProtocol.cmd_pwm_servo_several` was packing
`motion_time, count, [id, pulse]...` but the RRC Lite protocol requires a
leading `0x01` subcommand byte (`PWM_SERVO_CMD_SEVERAL`) before the
motion time. The data length was also wrong (3N+3 instead of 3N+4).

This meant **all multi-servo gimbal frames were malformed** and the board
silently ignored them — the gimbal never moved. The single-servo command
(`cmd_pwm_servo_single`) was already correct.

Fixed in `protocol.py` by prepending `cls.PWM_SERVO_CMD_SEVERAL` to the
packed parameters.

### 2. rclpy 10.0.10 pybind11 crash (Python 3.14)

Intermittent `RuntimeError: Unable to convert call argument '0' to Python
object` in `rclpy.executors.Executor._take_subscription` →
`sub.handle.take_message()`. Happens when converting `sensor_msgs/Joy.buttons`
(integer array) from C++ to Python. Uncaught in rclpy → kills the node →
launch tears down all nodes (looks like everything died).

**Workaround:** `resilient_spin()` helper in `logging_utils.py` wraps
`rclpy.spin_once()` in a loop and catches the `RuntimeError`, logging a
warning and continuing. All nodes now use `resilient_spin(node)` instead
of `rclpy.spin(node)`. This is an upstream rclpy bug, not our code.

## Next Steps

1. **Camera calibration** — generate a camera_info YAML for `/image_raw`
   (needed for CV/AI later; not needed for streaming).
2. **Migrate `buzzer_node`** to the gateway pattern (low priority) — it
   still opens its own serial port (Slice 1 test code).
