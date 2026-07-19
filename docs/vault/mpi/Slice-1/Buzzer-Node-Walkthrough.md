# Buzzer Node Walkthrough: `buzzer_node.py`

> Part of [[Slice-1-Overview]]. See also: [[Protocol-Implementation]], [[ROS2-Nodes-and-Topics]], [[ROS2-Parameters]]

This document walks through `mentorpi_driver/buzzer_node.py` — the proof-of-life node that beeps the buzzer every 5 seconds.

## File Location

```
ros2_ws/src/mentorpi_driver/mentorpi_driver/buzzer_node.py
```

## Purpose

This is the simplest possible test that the entire serial communication chain works. If the buzzer sounds, we know:
- The serial port is correctly configured
- The protocol implementation produces valid frames
- The CRC8 checksum is correct
- The RRC Lite board is receiving and understanding our commands

## Full Code Walkthrough

### Imports

```python
import serial
import rclpy
from rclpy.node import Node

from .protocol import RRCLiteProtocol
```

- `serial` — pyserial for serial port access
- `rclpy` — the ROS2 Python client library
- `Node` — base class for all ROS2 nodes
- `RRCLiteProtocol` — our protocol builder (see [[Protocol-Implementation]])

The `from .protocol` uses a **relative import** — the `.` means "from the same package". This is why the file must be inside the `mentorpi_driver/` Python package directory.

### The Node Class

```python
class BuzzerNode(Node):
    """Beeps the buzzer every 5 seconds as a proof-of-life test."""

    def __init__(self):
        super().__init__('buzzer_node')
```

Every ROS2 node inherits from `Node`. The `super().__init__('buzzer_node')` call:
- Registers the node with the name `buzzer_node`
- This name appears in `ros2 node list`
- Other nodes can find it by this name

### Parameters

```python
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value

        self.get_logger().info(f'BuzzerNode starting. Port={port}, Baud={baudrate}')
```

We declare two parameters with defaults:
- `port` — the serial port device path (default `/dev/ttyACM0`)
- `baudrate` — serial speed (default 1000000, i.e., 1 Mbps)

These can be overridden from the command line:
```bash
ros2 run mentorpi_driver buzzer_node --ros-args -p port:=/dev/ttyUSB0
```

See [[ROS2-Parameters]] for more on parameters.

### Opening the Serial Port

```python
        try:
            self.serial_conn = serial.Serial(
                port,
                baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02,
            )
            self.get_logger().info('Serial port opened. Buzzer will beep every 5 seconds.')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            self.serial_conn = None
            return
```

We wrap the serial port opening in a `try/except` because it can fail (port doesn't exist, permissions, already in use). If it fails, we log the error and set `serial_conn = None` so the node doesn't crash — it just won't be able to send commands.

See [[Serial-Communication]] for details on the serial settings.

### The Timer

```python
        self.counter = 0
        self.timer = self.create_timer(5.0, self.timer_callback)
```

`create_timer(5.0, callback)` calls `self.timer_callback` every 5.0 seconds. The timer runs inside `rclpy.spin()`, so it only fires while the node is spinning.

We also initialize a `counter` to track how many beeps we've sent — useful for logging.

### The Timer Callback

```python
    def timer_callback(self):
        """Send a buzzer command: 1400Hz, 100ms on, 100ms off, 2 cycles."""
        self.get_logger().info(f'Buzzer beep #{self.counter}')
        cmd = RRCLiteProtocol.cmd_buzzer(
            frequency_hz=1400,
            on_time_ms=100,
            off_time_ms=100,
            cycles=2,
        )
        self.serial_conn.write(cmd)
        self.counter += 1
```

Every 5 seconds:
1. Log which beep number we're on
2. Build a buzzer command packet using `RRCLiteProtocol.cmd_buzzer()`
3. Write the packet to the serial port
4. Increment the counter

The command: 1400 Hz tone, 100ms on, 100ms off, 2 cycles. This produces a quick "beep-beep" that's easy to hear and recognize.

### The `main()` Function

```python
def main(args=None):
    rclpy.init(args=args)
    node = BuzzerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Send a stop buzzer command (0 Hz, 0 cycles) to silence the buzzer
        if node.serial_conn:
            stop_cmd = RRCLiteProtocol.cmd_buzzer(0, 0, 0, 0)
            node.serial_conn.write(stop_cmd)
            node.get_logger().info('Sent buzzer stop command.')
        node.destroy_node()
        rclpy.shutdown()
```

This is the standard ROS2 node entry point:

1. `rclpy.init(args)` — initialize ROS2 (must be called once)
2. `BuzzerNode()` — create the node instance
3. `rclpy.spin(node)` — run the event loop (processes timers and callbacks). This blocks until the node is killed.
4. `except KeyboardInterrupt` — catch `Ctrl+C` gracefully
5. `finally` — **this is the important part we added**:
   - Send a buzzer-stop command (0 Hz, 0 cycles) to silence any ongoing beeps
   - Destroy the node and shut down ROS2

### The Shutdown Fix

> [!note] Why we added the stop command
> Initially, the node had no shutdown handler. When you pressed `Ctrl+C`, the node exited immediately, but the RRC Lite board was still executing the last buzzer command (which could have many cycles remaining). The buzzer would keep sounding for several seconds after the node was gone.
>
> The fix: send a buzzer command with 0 Hz and 0 cycles in the `finally` block. This immediately stops any ongoing buzzer activity.

### Entry Point

```python
if __name__ == '__main__':
    main()
```

This allows the file to be run directly (`python3 buzzer_node.py`) for debugging, but the normal way is via the entry point in `setup.py`:

```python
# In setup.py:
'buzzer_node = mentorpi_driver.buzzer_node:main',
```

This makes `ros2 run mentorpi_driver buzzer_node` work. See [[ROS2-Python-Packages]] for more on entry points.

## Running the Node

```bash
# Build first (if you changed anything)
cd ~/dev/mpi/ros2_ws
./build.sh --packages-select mentorpi_driver

# Source the workspace
source activate.sh

# Run the node
ros2 run mentorpi_driver buzzer_node
```

Or build and activate in one step:

```bash
source build.sh --packages-select mentorpi_driver
```

You should see:
```
[INFO] [buzzer_node]: BuzzerNode starting. Port=/dev/ttyACM0, Baud=1000000
[INFO] [buzzer_node]: Serial port opened. Buzzer will beep every 5 seconds.
[INFO] [buzzer_node]: Buzzer beep #0
[INFO] [buzzer_node]: Buzzer beep #1
...
```

Press `Ctrl+C` to stop. The buzzer should fall silent immediately.

## Key Concepts Demonstrated

1. **ROS2 node structure** — `__init__`, timer, callback, `main()`
2. **Parameters** — configurable serial port and baud rate
3. **Error handling** — graceful degradation when serial port fails
4. **Timers** — periodic actions without blocking
5. **Clean shutdown** — sending stop commands before exit
6. **Protocol usage** — importing and using `RRCLiteProtocol`

## Next Steps

- [[Serial-Driver-Node-Walkthrough]] — a more complex node with subscriptions
- [[Building-and-Testing]] — building and running this node
- [[Slice-1-Overview]] — back to the slice overview
