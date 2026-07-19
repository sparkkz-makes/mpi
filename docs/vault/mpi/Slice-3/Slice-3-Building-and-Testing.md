# Slice 3: Building and Testing

> Part of [[Slice-3-Overview]]. See also: [[Motor-Driver-Node-Walkthrough]], [[ROS2-Workspace-Setup]], [[ROS2-Running-Nodes]]

## Prerequisites

- [[Slice-1-Overview]] complete (serial communication verified)
- [[Slice-2-Overview]] complete (teleop publishes to `/cmd_vel`)
- RRC Lite board powered on and connected via USB
- `teleop_twist_keyboard` installed (comes with ROS2 Jazzy)

## Building

Use the workspace build script (it uses the workspace venv and redirects colcon logs to `build_logs`):

```bash
cd ~/dev/mpi/ros2_ws
./build.sh --packages-select mentorpi_driver
source activate.sh
```

Or build and activate in one step:

```bash
source build.sh --packages-select mentorpi_driver
```

Verify the motor driver entry point is registered:

```bash
ros2 pkg executables mentorpi_driver
# Should show: mentorpi_driver motor_driver
```

## Running the Full Chain

You need **two terminals** (or SSH sessions):

### Terminal 1: Motor Driver

```bash
source ~/dev/mpi/ros2_ws/activate.sh
ros2 run mentorpi_driver motor_driver
```

Expected output:
```
[INFO] [motor_driver]: MotorDriverNode starting. Port=/dev/ttyACM0, Baud=1000000
[INFO] [motor_driver]:   wheel_radius=0.0325 m, track_width=0.1 m
[INFO] [motor_driver]:   motor_ids=[0, 2, 1, 3], invert_motors=[True, False, True, False], max_wheel_speed=2.0 r/s
[INFO] [motor_driver]: Serial port opened successfully.
[WARN] [motor_driver]: Watchdog: no cmd_vel for 0.500s — stopping motors
[INFO] [motor_driver]: Heartbeat: STOPPED, last_cmd=5.000s ago, v=0.00, ω=0.00
```

### Terminal 2: Teleop

```bash
source ~/dev/mpi/ros2_ws/activate.sh
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

### Terminal 3 (Optional): Monitor `/cmd_vel`

```bash
source ~/dev/mpi/ros2_ws/activate.sh
ros2 topic echo /cmd_vel
```

## Driving the Robot

In the teleop terminal:

| Key | Action |
|-----|--------|
| `i` | Forward |
| `,` | Backward |
| `j` | Turn left |
| `l` | Turn right |
| `k` or any other key | Stop |
| `z` | Decrease speed by 10% |
| `q` | Increase speed by 10% |

> [!warning] Start slow!
> Press `z` a few times before driving to lower the speed. The default is 0.5 m/s which may be fast for indoor testing. The motor driver also clamps to `max_wheel_speed` (2.0 r/s ≈ 0.41 m/s).

> [!important] Keep the robot elevated
> During testing, suspend the robot so the wheels are off the ground. This prevents it from driving off the table.

## What You Should See

### Motor Driver Logs

When you press `i`:
```
[INFO] [motor_driver]: Received movement command: v=0.41 m/s, ω=0.00 rad/s
[INFO] [motor_driver]: Heartbeat: RUNNING, last_cmd=0.053s ago, v=0.41, ω=0.00
```

When you release the key (stop pressing):
```
[WARN] [motor_driver]: Watchdog: no cmd_vel for 0.524s — stopping motors
[INFO] [motor_driver]: Heartbeat: STOPPED, last_cmd=5.000s ago, v=0.00, ω=0.00
```

### Physical Robot

- Press `i` → all four wheels spin forward
- Press `,` → all four wheels spin backward
- Press `j` → left wheels reverse, right wheels forward (turn left)
- Press `l` → left wheels forward, right wheels reverse (turn right)
- Release keys → motors stop within 0.5 seconds

## Adjusting Parameters

### Lower max speed

```bash
ros2 run mentorpi_driver motor_driver --ros-args -p max_wheel_speed:=1.0
```

### Change serial port

```bash
ros2 run mentorpi_driver motor_driver --ros-args -p port:=/dev/ttyUSB0
```

### Longer watchdog (smoother but less safe)

```bash
ros2 run mentorpi_driver motor_driver --ros-args -p watchdog_timeout:=1.0
```

## Troubleshooting

### Motors don't move

1. Check the motor driver logs — is it receiving `/cmd_vel`? (Look for "Received movement command")
2. Check the serial port opened successfully
3. Verify the RRC Lite board is powered on
4. Check motor connections to the board

### Motors move in wrong direction

The `invert_motors` parameter may need adjusting. See [[Motor-Mapping-Discovery]] for how to determine the correct inversion pattern.

### Robot keeps moving after key release

The watchdog timeout may be too long. The default is 0.5s. If you changed it, reset it:

```bash
ros2 run mentorpi_driver motor_driver --ros-args -p watchdog_timeout:=0.5
```

### Pi reboots during operation

Check for undervoltage warnings:
```bash
journalctl --no-pager -b -1 | grep -i undervoltage
```

If present, use a separate power supply for the Pi, or run on battery. See [[Slice-3-Overview]] for more on the power issue we encountered.

### Board becomes unresponsive

If you sent an invalid motor ID (e.g., 4), the board may crash. Power cycle the RRC Lite board to recover.

## Direct Motor Testing (Without ROS2)

To test motors without ROS2, you can send commands directly:

```bash
python3 -c "
import sys, time
sys.path.insert(0, '~/dev/mpi/ros2_ws/src/mentorpi_driver')
from mentorpi_driver.protocol import RRCLiteProtocol
import serial

ser = serial.Serial('/dev/ttyACM0', 1000000, timeout=0.1)

# Spin motor 0 at 1.0 r/s for 3 seconds
cmd = RRCLiteProtocol.cmd_motor_single(0, 1.0)
ser.write(cmd)
time.sleep(3)
ser.write(RRCLiteProtocol.cmd_motor_stop_single(0))
ser.close()
"
```

## Verification Checklist

- [ ] `./build.sh` succeeds with no errors
- [ ] `ros2 run mentorpi_driver motor_driver` starts and opens serial port
- [ ] Motor driver receives `/cmd_vel` messages (check logs)
- [ ] All four wheels spin forward when pressing `i`
- [ ] Robot turns left/right with `j`/`l`
- [ ] Robot reverses with `,`
- [ ] Motors stop within 0.5s of key release
- [ ] Heartbeat logs appear every 5 seconds
- [ ] No crashes or reboots during operation

## Next Steps

- [[Slice-3-Overview]] — back to the slice overview
- [[Motor-Driver-Node-Walkthrough]] — the code behind the node
- [[Slice-4-Overview]] — wireless game controller (not yet written)
