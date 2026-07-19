# Running ROS2 Nodes

> Part of the [[ROS2-How-To]] series. See also: [[ROS2-Nodes-and-Topics]], [[ROS2-Parameters]]

## Prerequisites

Before running any nodes, make sure your environment is set up:

```bash
source ~/dev/mpi/ros2_ws/activate.sh
```

Or if this is in your `~/.bashrc`, just open a new terminal.

## `ros2 run` — The Basic Way

The simplest way to run a node:

```bash
ros2 run <package_name> <entry_point_name>
```

For our project:

```bash
ros2 run mentorpi_driver buzzer_node
```

This:
1. Finds the `mentorpi_driver` package
2. Looks up the `buzzer_node` entry point (defined in `setup.py`)
3. Runs the `main()` function

### Passing Parameters

Use `--ros-args -p name:=value`:

```bash
ros2 run mentorpi_driver buzzer_node --ros-args -p port:=/dev/ttyUSB0
ros2 run mentorpi_driver serial_driver --ros-args -p baudrate:=115200
```

Multiple parameters:

```bash
ros2 run mentorpi_driver buzzer_node \
    --ros-args \
    -p port:=/dev/ttyUSB0 \
    -p baudrate:=115200
```

### Remapping Topics

If a node publishes to `/cmd_vel` but you want it on `/robot/cmd_vel`:

```bash
ros2 run mentorpi_driver serial_driver --ros-args -r test_led:=/my_topic
```

## Stopping a Node

Press `Ctrl+C` in the terminal where the node is running. This sends SIGINT, which `rclpy.spin()` catches and allows clean shutdown.

In our `buzzer_node`, the `finally` block sends a stop command before shutting down:

```python
finally:
    if node.serial_conn:
        stop_cmd = RRCLiteProtocol.cmd_buzzer(0, 0, 0, 0)
        node.serial_conn.write(stop_cmd)
    node.destroy_node()
    rclpy.shutdown()
```

## Running Multiple Nodes

Each `ros2 run` starts one node in one terminal. For a real robot, you'll have many nodes running simultaneously. Options:

### Option 1: Multiple Terminals
Open a new terminal for each node. Simple but tedious.

### Option 2: Background Processes
```bash
ros2 run mentorpi_driver serial_driver &
ros2 run mentorpi_driver buzzer_node &
```

### Option 3: Launch Files (Recommended)
Create a launch file that starts multiple nodes at once. We'll cover this in a future slice.

## Inspecting Running Nodes

Once a node is running, open another terminal to inspect:

```bash
ros2 node list                    # See all running nodes
ros2 topic list                  # See all active topics
ros2 node info /buzzer_node       # See what a specific node is doing
ros2 topic echo /test_led         # Watch messages on a topic
```

## Common Issues

### "Package 'mentorpi_driver' not found"
You haven't sourced your workspace:
```bash
source ~/dev/mpi/ros2_ws/activate.sh
```

### "No executable found"
The entry point name doesn't match what's in `setup.py`. Check the `entry_points` section and rebuild with `./build.sh`.

### "Failed to open serial port"
The serial port doesn't exist or you don't have permission. Check:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
sudo usermod -aG dialout $USER   # Add yourself to the dialout group, then log out/in
```

### Node starts but immediately exits
You're missing `rclpy.spin(node)` in your `main()`. Without it, the node has nothing keeping it alive.

## Next Steps

- [[Building-and-Testing]] — building and running the buzzer node end-to-end
- [[Buzzer-Node-Walkthrough]] — the code behind the buzzer node
- [[ROS2-Parameters]] — more on parameters
