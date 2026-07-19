# Slice 4: Wireless Game Controller — Progress Log

## Status: IN PROGRESS (2026-07-14)

## What's Done

### 1. Controller Detection ✓
- **Device:** `/dev/input/js0` (world-readable, no udev rule needed)
- **Name:** SHANWAN Android Gamepad
- **Vendor/Product:** `2563:0526` (USB HID, bustype 0003)
- **8 axes, 15 buttons**

### 2. Controller Mapping ✓
Full mapping verified by hand with `joy_inspector` utility.

**Axes (0-indexed):**
| Idx | Name | Control | Rest | Direction |
|-----|------|---------|------|----------|
| 0 | X | Left stick H | 0 | right=-1.0, left=+1.0 **INVERTED** |
| 1 | Y | Left stick V | 0 | up=+1.0, down=-1.0 |
| 2 | Z | Right stick H | 0 | right=-1.0, left=+1.0 **INVERTED** |
| 3 | Rz | Right stick V | 0 | up=+1.0, down=-1.0 |
| 4 | Gas | R2 trigger | +1.0 | pressed→-1.0 (over-sensitive) |
| 5 | Brake | L2 trigger | +1.0 | pressed→-1.0 |
| 6 | Hat0X | D-pad H | 0 | left=+1.0, right=-1.0 **INVERTED** |
| 7 | Hat0Y | D-pad V | 0 | up=+1.0, down=-1.0 |

**Buttons (0-indexed):**
| Idx | Name | Idx | Name |
|-----|------|-----|------|
| 0 | A | 8 | TL2 (L2 btn) |
| 1 | B | 9 | TR2 (R2 btn) |
| 2 | C (unused) | 10 | Select |
| 3 | X | 11 | Start |
| 4 | Y | 12 | Mode |
| 5 | Z (unused) | 13 | ThumbL (L-stick click) |
| 6 | TL (L1) | 14 | ThumbR (R-stick click) |
| 7 | TR (R1) | | |

### 3. joy_inspector Utility ✓
- Custom node `mentorpi_driver/joy_inspector.py`
- Live in-place display of axes (bars) and buttons (■/·)
- Entry point: `ros2 run mentorpi_driver joy_inspector`

### 4. teleop_twist_joy Config ✓
- Config file: `config/teleop_joy_params.yaml`
- Launch file: `launch/gamepad_teleop.launch.py`
- Control scheme:
  - **Left stick Y (axis 1)** → linear.x (forward/back), scale 0.5 m/s
  - **Left stick X (axis 0)** → angular.z (turn), scale -1.0 (inverted)
  - **Right stick X (axis 2)** → linear.y (strafe, for mecanum), scale -0.5
  - **A button (0)** → deadman switch (must hold to move)
  - **R1 bumper (7)** → turbo button (2x speed)
  - Turbo scales: linear 1.0 m/s, angular 2.0 rad/s

## What's Next

### 5. Test & Tune ⬜
- Run `ros2 launch mentorpi_driver gamepad_teleop.launch.py`
- Verify: hold A + push left stick up → robot drives forward
- Verify: hold A + push left stick left/right → robot turns
- Tune scales if too fast/slow
- Test turbo (R1) feels right

### 6. Safety Review ⬜
- Confirm motors stop when A is released (deadman)
- Confirm watchdog in motor_driver still works (0.5s timeout)
- Test emergency stop (Select button? or just release A)

## Files Created
- `ros2_ws/src/mentorpi_driver/mentorpi_driver/joy_inspector.py` — live gamepad display
- `ros2_ws/src/mentorpi_driver/config/teleop_joy_params.yaml` — joy→cmd_vel mapping
- `ros2_ws/src/mentorpi_driver/launch/gamepad_teleop.launch.py` — full stack launch

## Quirks to Remember
- Triggers report +1.0 at rest, -1.0 pressed (inverted from normal expectation)
- Left stick X and Right stick X are both inverted (right = -1.0)
- D-pad X is inverted (left = +1.0)
- Buttons C(2) and Z(5) exist in jstest but seem unused by this pad
- R2 trigger (Gas, axis 4) is over-sensitive
