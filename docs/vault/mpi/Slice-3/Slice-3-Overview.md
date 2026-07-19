# Slice 3: Motor Control with Encoders

> Part of the [[Project-Overview]]. Prerequisite: [[Slice-2-Overview]]. See also: [[ROS2-Nodes-and-Topics]], [[ROS2-Parameters]], [[Protocol-Implementation]]

## Objective

Implement a motor driver node that translates `/cmd_vel` Twist commands into raw serial motor commands, making the robot actually move in response to keyboard input.

## What We Built

### New file: `motor_driver.py`

A ROS2 node that closes the loop between teleop and hardware:

```
Keyboard → teleop_twist_keyboard → /cmd_vel (Twist) → motor_driver → serial → RRC Lite → motors
```

The node:
1. **Subscribes to `/cmd_vel`** — receives `geometry_msgs/Twist` messages
2. **Converts Twist → wheel speeds** — differential-drive kinematics (m/s → r/s)
3. **Sends motor commands at 20 Hz** — fixed-rate timer re-sends the last command
4. **Watchdog timer** — stops motors if no `/cmd_vel` for 0.5 seconds
5. **Heartbeat logging** — status every 5 seconds for crash diagnosis
6. **Clean shutdown** — stops all motors on exit

### Updated: `setup.py`

Added the `motor_driver` entry point:
```python
'motor_driver = mentorpi_driver.motor_driver:main',
```

## Detailed Walkthroughs

- [[Motor-Driver-Node-Walkthrough]] — line-by-line walkthrough of `motor_driver.py`
- [[Differential-Drive-Kinematics]] — the math behind Twist → wheel speeds
- [[Motor-Mapping-Discovery]] — how we found the motor IDs and inversion pattern
- [[Slice-3-Building-and-Testing]] — building, running, and verifying

## Key Discoveries

### Motor IDs are 0-indexed (not 1-4)

The protocol documentation uses motor IDs 1-4 in its examples, but the actual firmware uses **0-3**. Sending motor ID 4 crashes the board, requiring a power cycle to recover.

| Motor ID | Physical Position | Needs Inverting |
|----------|------------------|-----------------|
| 0 | Front Left | Yes |
| 1 | Rear Left | Yes |
| 2 | Front Right | No |
| 3 | Rear Right | No |

We discovered this through sequential spin tests — see [[Motor-Mapping-Discovery]].

### Motor direction inversion

Motors on the same side of the chassis need their directions inverted so that positive speed = forward on all wheels. The `invert_motors` parameter controls this per-motor.

### The RRC Lite has no watchdog

If the Pi crashes or loses connection, the RRC Lite **keeps running the last motor command indefinitely**. This is a significant safety concern. Our software watchdog handles the case where teleop stops sending commands, but it can't help if the Pi itself dies.

### Power stability matters

The Pi rebooted twice during testing due to **undervoltage** (visible in kernel logs: `hwmon hwmon3: Undervoltage detected!`). Running on battery instead of a shared PSU resolved this.

## Technical Details

### Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `port` | `/dev/ttyACM0` | Serial port device |
| `baudrate` | `1000000` | Serial baud rate (1 Mbps) |
| `wheel_radius` | `0.0325` | Wheel radius in metres |
| `track_width` | `0.10` | Distance between left/right wheels |
| `motor_ids` | `[0, 2, 1, 3]` | Motor IDs ordered [FL, FR, RL, RR] |
| `invert_motors` | `[True, False, True, False]` | Which motors to invert |
| `watchdog_timeout` | `0.5` | Stop motors after this many seconds without cmd_vel |
| `max_wheel_speed` | `2.0` | Safety clamp on wheel speed (r/s) |

### Kinematics (Differential Drive)

For Slice 3, we use a simplified differential-drive model:

$$v_{left} = v - \omega \cdot \frac{W}{2}$$

$$v_{right} = v + \omega \cdot \frac{W}{2}$$

$$\text{rps} = \frac{v}{2\pi r}$$

Where:
- $v$ = `linear.x` (m/s)
- $\omega$ = `angular.z` (rad/s)
- $W$ = track width (m)
- $r$ = wheel radius (m)

Full Mecanum kinematics with strafing comes in [[Slice-5-Overview]].

### Command Rate

The node sends motor commands at a fixed **20 Hz** rate (every 50ms), not just when a `/cmd_vel` message arrives. This ensures:
- The RRC Lite keeps receiving commands
- The watchdog can detect stale commands
- Movement is smooth

## Verification Results

✅ All 4 motors respond to commands (IDs 0-3)
✅ All wheels drive forward when `i` is pressed
✅ Robot turns left/right with `j`/`l`
✅ Robot reverses with `,`
✅ Motors stop within 0.5s of key release (watchdog)
✅ Full chain works: keyboard → teleop → /cmd_vel → motor_driver → RRC Lite → motors
✅ Node runs stably for extended periods
✅ Heartbeat logging provides crash diagnosis data

## What's Next?

- **Encoder feedback** (`/joint_states`) — the protocol doc doesn't document a dedicated encoder read command. This will need further investigation, possibly requiring firmware support or reading IMU data (Func 7).
- [[Slice-4-Overview]] — Wireless game controller (replacing keyboard with joystick)
- [[Slice-5-Overview]] — Full Mecanum kinematics (strafing with `linear.y`)

## Next Steps

- [[Motor-Driver-Node-Walkthrough]] — the code behind the motor driver
- [[Differential-Drive-Kinematics]] — the math
- [[Motor-Mapping-Discovery]] — how we found the motor IDs
- [[Slice-3-Building-and-Testing]] — how to run it
- [[Slice-2-Overview]] — the prerequisite slice
- [[Project-Overview]] — the full project plan
