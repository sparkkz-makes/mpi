# Serial Driver Node Walkthrough: `serial_driver.py`

> Part of [[Slice-1-Overview]]. See also: [[Buzzer-Node-Walkthrough]], [[ROS2-Nodes-and-Topics]], [[Protocol-Implementation]]

This document walks through `mentorpi_driver/serial_driver.py` — the ROS2 node that manages the serial connection and provides a topic-based interface for triggering commands.

## File Location

```
ros2_ws/src/mentorpi_driver/mentorpi_driver/serial_driver.py
```

## Purpose

The serial driver node is the **central serial communication hub**. In Slice 1, it provides a simple proof-of-life test: subscribe to a `test_led` topic and blink an LED when a message arrives.

In future slices, this node will be the single owner of the serial port. Other nodes (motor driver, gimbal controller, etc.) will send commands via ROS2 topics, and this node will translate them into serial frames.

```
  ┌─────────────┐     test_led (String)     ┌──────────────────┐    serial    ┌──────────┐
  │ CLI / other │ ────────────────────────► │ SerialDriverNode │ ───────────► │ RRC Lite │
  │ nodes       │                           │                  │   (UART)     │ Board    │
  └─────────────┘                           └──────────────────┘              └──────────┘
```

## Full Code Walkthrough

### Imports

```python
import serial
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .protocol import RRCLiteProtocol
```

Compared to `buzzer_node.py`, this file also imports `String` from `std_msgs.msg` — the message type for the `test_led` topic.

### The Node Class

```python
class SerialDriverNode(Node):
    """ROS2 node that manages serial communication with the RRC Lite board."""

    def __init__(self):
        super().__init__('serial_driver')
```

The node is named `serial_driver` — this shows up in `ros2 node list` as `/serial_driver`.

### Parameters and Serial Connection

```python
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value

        self.get_logger().info(f'Opening serial port {port} at {baudrate} baud...')

        try:
            self.serial_conn = serial.Serial(
                port,
                baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02,
            )
            self.get_logger().info('Serial port opened successfully.')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            self.serial_conn = None
```

Same pattern as the buzzer node — declare parameters, open the serial port, handle errors gracefully. See [[Buzzer-Node-Walkthrough]] for a detailed explanation of this pattern.

### The Subscription

```python
        self.sub_test = self.create_subscription(
            String, 'test_led', self.test_led_callback, 10
        )
```

This is the key difference from the buzzer node. Instead of a timer, this node **subscribes** to a topic:

| Argument | Value | Meaning |
|----------|-------|---------|
| Message type | `String` | Messages contain a single string field |
| Topic name | `test_led` | A relative name — becomes `/serial_driver/test_led` |
| Callback | `self.test_led_callback` | Called when a message arrives |
| QoS depth | `10` | Buffer up to 10 messages |

### The `send_command` Method

```python
    def send_command(self, frame: bytes) -> None:
        """Send a raw frame to the RRC Lite board."""
        if not self.serial_conn:
            self.get_logger().warn('Serial connection not active. Cannot send.')
            return
        self.serial_conn.write(frame)
```

A reusable method for sending any frame. It checks if the serial connection is active before writing. This will be used by future nodes that send commands through this driver.

### The Subscription Callback

```python
    def test_led_callback(self, msg: String) -> None:
        """
        Called when a message arrives on 'test_led'.
        Blinks LED 1 for 5 cycles (100ms on, 100ms off).
        """
        self.get_logger().info(f'Received test command: "{msg.data}". Blinking LED...')
        cmd = RRCLiteProtocol.cmd_led(1, 100, 100, 5)
        self.send_command(cmd)
```

When a `String` message arrives on the `test_led` topic:
1. Log the message content
2. Build an LED command: LED 1, 100ms on, 100ms off, 5 cycles
3. Send it via `send_command()`

The `msg.data` field contains the string — we log it but don't use it for anything. In a more sophisticated version, the string could specify which LED or blink pattern.

### The `main()` Function

```python
def main(args=None):
    rclpy.init(args=args)
    node = SerialDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
```

Standard ROS2 entry point. Note that unlike the buzzer node, there's no shutdown command to send — the LED command is fire-and-forget and completes on its own.

## Using the Node

### Running the Driver

```bash
# Terminal 1: Start the serial driver
ros2 run mentorpi_driver serial_driver
```

### Triggering the LED

```bash
# Terminal 2: Send a message to trigger the LED blink
ros2 topic pub /serial_driver/test_led std_msgs/String '{data: "blink"}' --once
```

You should see in Terminal 1:
```
[INFO] [serial_driver]: Received test command: "blink". Blinking LED...
```

### Inspecting the Node

```bash
# See what topics the node subscribes to
ros2 node info /serial_driver

# List all topics
ros2 topic list
# Should show /serial_driver/test_led
```

## Topic Names: Relative vs Absolute

The subscription uses a **relative** topic name (`test_led` without a leading `/`). ROS2 resolves this relative to the node's namespace, so it becomes `/serial_driver/test_led`.

If you wanted an absolute name (accessible regardless of node namespace), use `/test_led`:

```python
self.create_subscription(String, '/test_led', self.callback, 10)
```

For now, the relative name is fine since we're just testing. In later slices, we'll use absolute names for topics that multiple nodes need to find.

## Comparison: `serial_driver.py` vs `buzzer_node.py`

| Aspect | `buzzer_node.py` | `serial_driver.py` |
|--------|-------------------|---------------------|
| Trigger | Timer (every 5s) | Topic subscription |
| Command | Buzzer | LED |
| Use case | Standalone proof-of-life | Central serial hub |
| Future role | Will be removed | Will be expanded |

The buzzer node is a **standalone test** — it opens its own serial connection and sends commands on a timer. The serial driver is the **foundation for future work** — it will own the serial port and relay commands from other nodes.

> [!important] Serial port ownership
> Only one process can open a serial port at a time. If you run both `buzzer_node` and `serial_driver` simultaneously, the second one to start will fail with "device busy". In future slices, only the serial driver will open the port, and other nodes will communicate via topics.

## Future Evolution

In later slices, this node will:
- Subscribe to `/cmd_vel` (Twist messages) and translate them to motor commands
- Publish encoder feedback to `/joint_states`
- Subscribe to gimbal commands and translate them to servo commands
- Handle incoming serial data (encoder readings, IMU data) and publish it as ROS2 topics

## Next Steps

- [[Building-and-Testing]] — building and running both nodes
- [[Buzzer-Node-Walkthrough]] — the simpler node for comparison
- [[Slice-1-Overview]] — back to the slice overview
