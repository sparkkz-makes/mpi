# Slice 2: PC Teleoperation

> Part of the [[Project-Overview]]. Prerequisite: [[Slice-1-Overview]]. See also: [[ROS2-Nodes-and-Topics]], [[ROS2-Running-Nodes]]

## Objective

Enable manual control of the robot by bridging keyboard input from the PC to the Raspberry Pi. A teleop node captures keypresses and publishes `geometry_msgs/Twist` velocity commands to the `/cmd_vel` topic.

## What We Did

Slice 2 is lighter on code than Slice 1 — we leveraged an existing ROS2 package rather than writing our own. The work was:

1. **Verified `teleop_twist_keyboard` is installed** — it ships with ROS2 Lyrical as `ros-lyrical-teleop-twist-keyboard`
2. **Ran the teleop node** — it publishes `geometry_msgs/Twist` messages to `cmd_vel`
3. **Verified messages arrive** — used `ros2 topic echo /cmd_vel` to confirm Twist messages appear when keys are pressed

No new code was written for this slice. The teleop node is a standard ROS2 tool that works out of the box.

## The `teleop_twist_keyboard` Node

### What It Does

`teleop_twist_keyboard` is a standard ROS2 package that reads raw keyboard input and translates it into `geometry_msgs/Twist` messages. It's robot-agnostic — it doesn't know or care what hardware receives the commands.

```
  Keyboard ──► teleop_twist_keyboard ──► /cmd_vel (Twist) ──► [motor driver in Slice 3]
```

### Key Bindings

The node displays this help text when it starts:

```
Moving around:
   u    i    o
   j    k    l
   m    ,    .

For Holonomic mode (strafing), hold down the shift key:
---------------------------
   U    I    O
   J    K    L
   M    <    >

t : up (+z)
b : down (-z)

anything else : stop

q/z : increase/decrease max speeds by 10%
w/x : increase/decrease only linear speed by 10%
e/c : increase/decrease only angular speed by 10%

CTRL-C to quit
```

| Key | Action |
|-----|--------|
| `i` | Forward |
| `,` | Backward |
| `j` | Turn left |
| `l` | Turn right |
| `u` / `o` | Forward + turn |
| `m` / `.` | Backward + turn |
| `k` or any other key | Stop |
| `q` / `z` | Increase / decrease all speeds by 10% |
| `w` / `x` | Increase / decrease linear speed only |
| `e` / `c` | Increase / decrease angular speed only |

The **shifted** (uppercase) keys enable **holonomic mode** — they set the `linear.y` component for lateral strafing. This will matter in [[Slice-5-Overview]] when we implement full Mecanum kinematics.

### Default Speeds

- **Linear speed:** 0.5 m/s
- **Angular speed:** 1.0 rad/s

These can be adjusted at runtime with the `q`/`z`/`w`/`x`/`e`/`c` keys.

## The `geometry_msgs/Twist` Message

The `/cmd_vel` topic carries `geometry_msgs/Twist` messages. A Twist expresses velocity in free space, broken into linear and angular parts:

```
Vector3  linear
        float64 x    # Forward/backward velocity (m/s)
        float64 y    # Left/right velocity (m/s) — strafing
        float64 z    # Up/down velocity (m/s) — not used for ground robots
Vector3  angular
        float64 x    # Roll rate (rad/s) — not used
        float64 y    # Pitch rate (rad/s) — not used
        float64 z    # Yaw rate (rad/s) — rotation
```

For a ground robot like ours:
- `linear.x` → forward/backward
- `linear.y` → lateral strafing (Mecanum only — see [[Slice-5-Overview]])
- `angular.z` → rotation (turning)

### Example Messages

Pressing `i` (forward) at default speed:
```
linear:
  x: 0.5
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 0.0
```

Pressing `j` (turn left) at default speed:
```
linear:
  x: 0.0
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 1.0
```

Pressing `o` (forward + turn right):
```
linear:
  x: 0.5
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: -1.0
```

## How to Run It

### Terminal 1: Start the Teleop Node

```bash
source ~/dev/mpi/ros2_ws/activate.sh
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

You'll see the key bindings printed. The node is now waiting for keypresses.

> [!important] The terminal must have focus
> `teleop_twist_keyboard` reads raw keyboard input using `termios`. The terminal where it's running must be the active window — clicking elsewhere means your keypresses won't be captured.

### Terminal 2: Verify Messages (Optional)

```bash
source ~/dev/mpi/ros2_ws/activate.sh
ros2 topic echo /cmd_vel
```

Now press keys in Terminal 1. You'll see Twist messages appear in Terminal 2.

### Terminal 3: Inspect the Topic (Optional)

```bash
source ~/dev/mpi/ros2_ws/activate.sh

# See topic info
ros2 topic info /cmd_vel

# Check publish rate
ros2 topic hz /cmd_vel
```

### Stopping

Press `Ctrl+C` in the teleop terminal. The node exits and stops publishing.

## Running Over SSH (PC → Pi)

Since the teleop node runs on the Pi but you want to control it from your PC, you have two options:

### Option 1: SSH from the PC (Simplest)

```bash
# From your PC, SSH into the Pi
ssh stu@<pi-ip-address>

# Then run the teleop node
source ~/dev/mpi/ros2_ws/activate.sh
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

The keypresses from your SSH session are captured by the teleop node on the Pi. This works because SSH forwards your terminal input.

> [!note] This is the approach we verified
> We ran the teleop node over SSH and confirmed Twist messages appear on `/cmd_vel` using `ros2 topic echo` in a second terminal.

### Option 2: Run Teleop on the PC (Distributed ROS2)

If your PC also has ROS2 installed, you can run the teleop node on the PC and have it publish to the Pi's ROS2 network. This requires ROS2 DDS discovery between the two machines (same network, configured `ROS_DOMAIN_ID`). We won't cover this now — the SSH approach is simpler and sufficient.

## Topic Naming

The teleop node publishes to the **relative** topic name `cmd_vel`. Since the node is named `/teleop_twist_keyboard` and has no namespace, this resolves to `/cmd_vel` — the standard topic name that motor drivers expect.

If you needed a different topic name (e.g., `/robot/cmd_vel`), you could remap it:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/robot/cmd_vel
```

See [[ROS2-Running-Nodes]] for more on topic remapping.

## Verification Results

✅ `teleop_twist_keyboard` runs and displays key bindings
✅ Pressing movement keys publishes `geometry_msgs/Twist` messages to `/cmd_vel`
✅ `ros2 topic echo /cmd_vel` confirms messages arrive with correct `linear.x` and `angular.z` values
✅ Speed adjustment keys (`q`/`z` etc.) work as expected

## What's Next?

Right now, the Twist messages go nowhere — there's no node subscribing to `/cmd_vel` to actually move the motors. That's [[Slice-3-Overview]] (Motor Control with Encoders), where we'll:

1. Create a motor driver node that subscribes to `/cmd_vel`
2. Translate Twist commands into individual wheel speeds
3. Send motor commands to the RRC Lite via the serial protocol from [[Protocol-Implementation]]

The full control chain will be:

```
Keyboard → teleop_twist_keyboard → /cmd_vel (Twist) → motor_driver → serial → RRC Lite → motors
```

## Next Steps

- [[Slice-3-Overview]] — motor control (not yet written)
- [[Slice-1-Overview]] — the prerequisite slice
- [[ROS2-Nodes-and-Topics]] — background on topics and messages
- [[Project-Overview]] — the full project plan
