# Building and Testing: Slice 1

> Part of [[Slice-1-Overview]]. See also: [[ROS2-Workspace-Setup]], [[ROS2-Running-Nodes]], [[Buzzer-Node-Walkthrough]]

This document covers the practical steps to build, run, and verify the Slice 1 code.

## Prerequisites

- ROS2 Lyrical installed on the Raspberry Pi
- The RRC Lite board connected via USB and powered on
- The `mentorpi_driver` package in `~/dev/mpi/ros2_ws/src/`
- pyserial installed (`pip install pyserial` or it comes with the ROS2 setup)

### Verify the Serial Port

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

You should see `/dev/ttyACM0` (or similar). If not, check the USB connection and that the board is powered.

### Verify Permissions

```bash
# If you get "permission denied" when accessing the serial port:
sudo usermod -aG dialout $USER
# Then log out and back in (or reboot)
```

## Building the Package

### First-Time Build

Use the workspace build script, which activates the venv, redirects colcon logs to `build_logs`, and patches console script shebangs:

```bash
cd ~/dev/mpi/ros2_ws
./build.sh --packages-select mentorpi_driver
```

Expected output:
```
Starting >>> mentorpi_driver
Finished <<< mentorpi_driver [2.02s]

Summary: 1 package finished [2.29s]
```

### After Making Code Changes

Any time you edit files in `src/mentorpi_driver/`, rebuild:

```bash
cd ~/dev/mpi/ros2_ws
./build.sh --packages-select mentorpi_driver
```

> [!note] When to rebuild
> - **Always rebuild** if you changed `setup.py` (e.g., added a new entry point)
> - **Rebuild** if you changed `package.xml` (e.g., added a dependency)
> - **Rebuild recommended** after changing `.py` files (unless using `--symlink-install`)

### Source the Workspace

After building, source the workspace activation script so ROS2 can find your package and the venv is active:

```bash
source ~/dev/mpi/ros2_ws/activate.sh
```

Or build and activate in one step:

```bash
source build.sh --packages-select mentorpi_driver
```

Or open a new terminal (if this is in your `~/.bashrc`).

### Verify the Build

```bash
ros2 pkg list | grep mentorpi_driver
# Should output: mentorpi_driver
```

## Testing the Buzzer Node

This is the primary Slice 1 verification — if the buzzer sounds, the entire serial chain works.

### Run the Node

```bash
ros2 run mentorpi_driver buzzer_node
```

Expected output:
```
[INFO] [buzzer_node]: BuzzerNode starting. Port=/dev/ttyACM0, Baud=1000000
[INFO] [buzzer_node]: Serial port opened. Buzzer will beep every 5 seconds.
[INFO] [buzzer_node]: Buzzer beep #0
[INFO] [buzzer_node]: Buzzer beep #1
[INFO] [buzzer_node]: Buzzer beep #2
...
```

### What You Should Hear

Every 5 seconds: a quick "beep-beep" (1400 Hz, 100ms on, 100ms off, 2 cycles).

### Stop the Node

Press `Ctrl+C`. The node sends a stop command and exits:

```
^C[INFO] [buzzer_node]: Sent buzzer stop command.
```

The buzzer should fall silent immediately.

### With Different Parameters

If your serial port is different:

```bash
ros2 run mentorpi_driver buzzer_node --ros-args -p port:=/dev/ttyUSB0
```

## Testing the Serial Driver Node

The serial driver node is tested via the `test_led` topic.

### Terminal 1: Start the Driver

```bash
ros2 run mentorpi_driver serial_driver
```

Expected:
```
[INFO] [serial_driver]: Opening serial port /dev/ttyACM0 at 1000000 baud...
[INFO] [serial_driver]: Serial port opened successfully.
```

### Terminal 2: Trigger the LED

```bash
ros2 topic pub /serial_driver/test_led std_msgs/String '{data: "blink"}' --once
```

Expected in Terminal 1:
```
[INFO] [serial_driver]: Received test command: "blink". Blinking LED...
```

The LED on the RRC Lite board should blink 5 times (100ms on, 100ms off).

### Inspecting the ROS2 Graph

In a third terminal:

```bash
# List nodes
ros2 node list
# /serial_driver

# List topics
ros2 topic list
# /parameter_events
# /rosout
# /serial_driver/test_led

# See node info
ros2 node info /serial_driver
```

## Troubleshooting

### "Failed to open serial port: [Errno 2] No such file or directory"

The serial port doesn't exist. Check:
```bash
ls /dev/ttyACM* /dev/ttyUSB*
dmesg | tail  # See what happened when you plugged in the board
```

### "Failed to open serial port: [Errno 13] Permission denied"

Your user doesn't have permission to access the serial port:
```bash
sudo usermod -aG dialout $USER
# Log out and back in
```

### "Failed to open serial port: [Errno 16] Device or resource busy"

Another process has the port open. Serial ports are exclusive — only one process at a time. Kill any other nodes using the port:
```bash
ps aux | grep -E 'buzzer_node|serial_driver'
kill <PID>
```

### Buzzer doesn't sound but node runs without errors

1. **Check the baud rate** — must be 1000000 (1 Mbps). The default in our code is correct, but verify you didn't override it.
2. **Check the serial port** — make sure `/dev/ttyACM0` is actually the RRC Lite (not another USB device).
3. **Check the board is powered** — the USB cable provides data but the board needs its own power for the buzzer.
4. **Verify the packet** — run this to see the exact bytes being sent:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'src/mentorpi_driver')
   from mentorpi_driver.protocol import RRCLiteProtocol
   cmd = RRCLiteProtocol.cmd_buzzer(1400, 100, 100, 2)
   print(' '.join(f'{b:02X}' for b in cmd))
   "
   ```
   Expected: `AA 55 02 08 78 05 64 00 64 00 02 00 <checksum>`

### Buzzer keeps sounding after Ctrl+C

This was a bug we fixed. The node now sends a stop command in the `finally` block. If you're running an old version, rebuild:
```bash
./build.sh --packages-select mentorpi_driver
```

## What Success Looks Like

✅ `./build.sh` completes with no errors
✅ `ros2 run mentorpi_driver buzzer_node` starts and opens the serial port
✅ The buzzer sounds every 5 seconds
✅ `Ctrl+C` stops the node and the buzzer falls silent
✅ `ros2 run mentorpi_driver serial_driver` starts and subscribes to `test_led`
✅ Publishing to `test_led` causes the LED to blink

Once all of these pass, **Slice 1 is complete** and you're ready for [[Slice-2-Overview]] (PC Teleoperation).

## Next Steps

- [[Slice-1-Overview]] — back to the slice overview
- [[Project-Overview]] — the full project plan
- [[ROS2-Running-Nodes]] — more on running nodes
