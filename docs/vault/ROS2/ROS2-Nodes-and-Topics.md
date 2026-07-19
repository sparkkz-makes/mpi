# ROS2 Nodes and Topics

> Part of the [[ROS2-How-To]] series. See also: [[ROS2-Parameters]], [[Buzzer-Node-Walkthrough]]

## The Big Picture

ROS2 is a **communication framework** for robotics. Instead of one monolithic program, you write many small programs (**nodes**) that talk to each other by sending messages over **topics**. This modular design lets you swap components, debug individual pieces, and scale to complex systems.

```
  ┌──────────┐     /cmd_vel      ┌──────────────┐    serial     ┌──────────┐
  │ Teleop   │ ───────────────► │ Motor Driver │ ────────────► │ RRC Lite │
  │ Node     │   (Twist msg)     │ Node         │   (UART)      │ Board    │
  └──────────┘                   └──────────────┘               └──────────┘
```

## Nodes

A **node** is a single process that does one thing. In our project:

- `buzzer_node` — sends buzzer commands to the hardware
- `serial_driver` — manages the serial port and relays commands
- (future) `motor_driver` — translates `/cmd_vel` into motor speeds
- (future) `teleop` — reads keyboard/joystick and publishes `/cmd_vel`

Each node is an instance of `rclpy.node.Node` (in Python) or `rclcpp::Node` (in C++).

### Anatomy of a Python Node

```python
import rclpy
from rclpy.node import Node

class MyNode(Node):
    def __init__(self):
        super().__init__('my_node')          # Node name (visible in ros2 node list)
        self.get_logger().info('Hello!')

def main(args=None):
    rclpy.init(args=args)        # Initialize ROS2
    node = MyNode()              # Create the node
    rclpy.spin(node)             # Keep it running, processing callbacks
    node.destroy_node()          # Clean up
    rclpy.shutdown()             # Shut down ROS2

if __name__ == '__main__':
    main()
```

Key points:
- `rclpy.init()` — must be called once at the start of every ROS2 program
- `super().__init__('name')` — gives the node a name; this is what shows up in `ros2 node list`
- `rclpy.spin(node)` — blocks forever, processing timers and message callbacks. Without this, the node exits immediately.
- `node.destroy_node()` + `rclpy.shutdown()` — clean teardown

## Topics

A **topic** is a named channel for sending messages. Nodes can **publish** to a topic or **subscribe** to it. Think of it like a radio station: the publisher broadcasts, and anyone tuned in (subscribers) receives.

### Topic Properties

| Property | Description | Example |
|----------|-------------|---------|
| **Name** | The topic's address | `/cmd_vel` |
| **Message Type** | The structure of data sent | `geometry_msgs/msg/Twist` |
| **QoS** | Quality of Service (reliability, durability) | `10` (depth of queue) |

### Publishing

```python
from geometry_msgs.msg import Twist

class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

    def send_command(self):
        msg = Twist()
        msg.linear.x = 0.5    # Forward at 0.5 m/s
        msg.angular.z = 0.0   # No rotation
        self.pub.publish(msg)
```

The `10` in `create_publisher` is the **QoS depth** — how many messages to buffer if a subscriber isn't keeping up. For most cases, `10` is fine.

### Subscribing

```python
from std_msgs.msg import String

class ListenerNode(Node):
    def __init__(self):
        super().__init__('listener')
        self.sub = self.create_subscription(
            String,              # Message type
            'test_led',          # Topic name
            self.callback,       # Function to call when a message arrives
            10                   # QoS depth
        )

    def callback(self, msg: String):
        self.get_logger().info(f'Received: {msg.data}')
```

The callback is called automatically by `rclpy.spin()` whenever a new message arrives on the topic.

### Topic Names: Absolute vs Relative

- `/cmd_vel` — **absolute** (global namespace). Always refers to the same topic.
- `test_led` — **relative**. Gets prefixed with the node's namespace. For a node `/serial_driver`, this becomes `/serial_driver/test_led`.

Use absolute names (`/`) when you want nodes to find each other regardless of namespace.

## Messages

A **message** (msg) is a structured data type. Common ones:

| Message Type | What It Represents | Key Fields |
|--------------|-------------------|------------|
| `std_msgs/String` | A simple string | `data` (string) |
| `geometry_msgs/Twist` | Velocity command | `linear` (x,y,z), `angular` (x,y,z) |
| `sensor_msgs/JointState` | Joint positions/velocities | `name`, `position`, `velocity` |
| `sensor_msgs/Image` | Camera image | `data`, `width`, `height` |

You create a message instance, fill in its fields, and publish it. ROS2 handles serialization and delivery.

## Timers

Nodes often need to do things periodically (read sensors, send commands). Use a **timer**:

```python
class BuzzerNode(Node):
    def __init__(self):
        super().__init__('buzzer_node')
        self.timer = self.create_timer(5.0, self.timer_callback)

    def timer_callback(self):
        self.get_logger().info('Beep!')
```

`create_timer(period_seconds, callback)` calls `callback` every `period_seconds`. The callback runs inside `rclpy.spin()`.

## Inspecting the ROS2 Graph

Once nodes are running, you can inspect them from the terminal:

```bash
ros2 node list              # List all running nodes
ros2 topic list             # List all active topics
ros2 topic echo /cmd_vel    # Print messages arriving on /cmd_vel
ros2 topic info /cmd_vel    # Show publishers and subscribers
ros2 node info /buzzer_node  # Show a node's pubs, subs, and services
```

These are your debugging tools. If something isn't working, `ros2 topic echo` is usually the first thing to check.

## The Spin Loop

`rclpy.spin(node)` runs an event loop that:
1. Checks for new messages on subscribed topics → calls callbacks
2. Checks if any timers have fired → calls timer callbacks
3. Repeats forever

This is why you must call `spin` — without it, callbacks never run. If you need to do other work, you can use `spin_once()` or a multi-threaded executor, but `spin()` is the standard pattern.

## Next Steps

- [[ROS2-Parameters]] — how to make nodes configurable
- [[ROS2-Running-Nodes]] — running nodes from the command line
- [[Buzzer-Node-Walkthrough]] — see these concepts in real code
