# Motor Driver Node Walkthrough: `motor_driver.py`

> Part of [[Slice-3-Overview]]. See also: [[Protocol-Implementation]], [[ROS2-Nodes-and-Topics]], [[ROS2-Parameters]], [[Differential-Drive-Kinematics]]

This document walks through `mentorpi_driver/motor_driver.py` — the ROS2 node that translates velocity commands into motor motion.

## File Location

```
ros2_ws/src/mentorpi_driver/mentorpi_driver/motor_driver.py
```

## Purpose

The motor driver node is the bridge between high-level ROS2 velocity commands and the low-level RRC Lite motor controller. It:

1. Subscribes to `/cmd_vel` (Twist messages from teleop)
2. Converts linear/angular velocity into per-wheel speeds
3. Sends motor commands over serial at a fixed 20 Hz rate
4. Stops motors if no command is received within the watchdog timeout
5. Logs heartbeats for crash diagnosis

## Architecture

```
                          ┌─────────────────────────────────────┐
 /cmd_vel (Twist) ──────► │  MotorDriverNode                  │
                          │                                   │
                          │  cmd_vel_callback:                 │
                          │    stores latest Twist             │
                          │                                   │
                          │  command_callback (20 Hz timer):   │
                          │    if watchdog expired → stop      │
                          │    else → send wheel speeds        │ ──► serial ──► RRC Lite
                          │                                   │
                          │  heartbeat (every 5s):            │
                          │    log status                      │
                          └─────────────────────────────────────┘
```

The key design decision is the **fixed-rate command timer**. Instead of sending a motor command only when a `/cmd_vel` message arrives, the node stores the latest Twist and re-sends it 20 times per second. This means:
- The watchdog can detect stale commands (if teleop stops sending)
- Movement is smooth (commands are continuously refreshed)
- If the node dies, the board stops getting commands

## Code Walkthrough

### Imports

```python
import math
import serial
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist

from .protocol import RRCLiteProtocol
```

- `math` — for π in the wheel circumference calculation
- `serial` — pyserial for the serial port
- `ExternalShutdownException` — for clean shutdown when killed by SIGTERM
- `Twist` — the ROS2 velocity message type

### Parameters

The node declares many parameters, all with sensible defaults:

```python
self.declare_parameter('port', '/dev/ttyACM0')
self.declare_parameter('baudrate', 1000000)
self.declare_parameter('wheel_radius', 0.0325)   # metres
self.declare_parameter('track_width', 0.10)       # metres
self.declare_parameter('motor_ids', [0, 2, 1, 3])
self.declare_parameter('invert_motors', [True, False, True, False])
self.declare_parameter('watchdog_timeout', 0.5)
self.declare_parameter('max_wheel_speed', 2.0)
```

See [[ROS2-Parameters]] for more on parameters. The `motor_ids` and `invert_motors` parameters were discovered through hardware testing — see [[Motor-Mapping-Discovery]].

> [!important] Motor IDs are 0-indexed
> The protocol doc examples use IDs 1-4, but the firmware actually uses 0-3. Sending ID 4 crashes the board. See [[Motor-Mapping-Discovery]] for the full story.

### Serial Connection

Same pattern as the buzzer and serial driver nodes:

```python
try:
    self.serial_conn = serial.Serial(
        port, baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.02,
    )
except serial.SerialException as e:
    self.get_logger().error(f'Failed to open serial port: {e}')
    self.serial_conn = None
```

See [[Serial-Communication]] for details on the serial settings.

### ROS2 Interface

```python
self.cmd_vel_sub = self.create_subscription(
    Twist, '/cmd_vel', self.cmd_vel_callback, 10
)

self.last_twist = Twist()  # Defaults to all zeros (stopped)
self.last_cmd_time = self.get_clock().now()
self.command_timer = self.create_timer(0.05, self.command_callback)
```

The subscription stores incoming Twist messages. The **20 Hz timer** (`0.05` seconds = 50ms) does the actual command sending. `last_twist` starts as a zero-velocity Twist (all fields default to 0.0).

### Kinematics: `twist_to_wheel_speeds`

See [[Differential-Drive-Kinematics]] for the full math. The function:

1. Extracts `linear.x` (forward velocity) and `angular.z` (rotation rate)
2. Computes left/right side velocities using the differential drive formula
3. Converts m/s → revolutions per second using wheel circumference
4. Clamps to `max_wheel_speed` for safety
5. Applies per-motor direction inversion
6. Returns a list of `(motor_id, speed_rps)` tuples

### Command Sending

```python
def send_wheel_speeds(self, wheel_speeds):
    if not self.serial_conn:
        return
    cmd = RRCLiteProtocol.cmd_motor_multiple(wheel_speeds)
    self.serial_conn.write(cmd)

def stop_all_motors(self):
    if not self.serial_conn:
        return
    cmd = RRCLiteProtocol.cmd_motor_stop_several(0x0F)
    self.serial_conn.write(cmd)
    self.is_stopped = True
```

`cmd_motor_multiple` builds a single serial frame controlling all 4 motors at once. `cmd_motor_stop_several(0x0F)` sends a stop command using a bitmask (0x0F = bits 0-3 = motors 0-3).

### The `cmd_vel_callback`

```python
def cmd_vel_callback(self, msg: Twist):
    self.last_cmd_time = self.get_clock().now()
    was_stopped = self.is_stopped
    is_moving = abs(msg.linear.x) > 0.001 or abs(msg.angular.z) > 0.001
    if was_stopped and is_moving:
        self.get_logger().info(
            f'Received movement command: v={msg.linear.x:.2f} m/s, '
            f'ω={msg.angular.z:.2f} rad/s'
        )
    self.last_twist = msg
```

This callback **only stores** the latest Twist — it doesn't send anything. The actual sending happens in the timer. It logs state transitions (stopped → moving) at INFO level so you can see when commands arrive without flooding the log.

### The `command_callback` (20 Hz Timer)

```python
def command_callback(self):
    self._tick_count += 1
    elapsed = (self.get_clock().now() - self.last_cmd_time).nanoseconds / 1e9

    # Heartbeat every 5 seconds (100 ticks at 20 Hz)
    if self._tick_count % 100 == 0:
        status = 'STOPPED' if self.is_stopped else 'RUNNING'
        self.get_logger().info(
            f'Heartbeat: {status}, last_cmd={elapsed:.3f}s ago, '
            f'v={self.last_twist.linear.x:.2f}, '
            f'ω={self.last_twist.angular.z:.2f}'
        )

    if elapsed > self.watchdog_timeout:
        if not self.is_stopped:
            self.get_logger().warn(
                f'Watchdog: no cmd_vel for {elapsed:.3f}s — stopping motors'
            )
            self.stop_all_motors()
        return

    wheel_speeds = self.twist_to_wheel_speeds(self.last_twist)
    self.send_wheel_speeds(wheel_speeds)
    self.is_stopped = False
```

This runs 20 times per second and does three things:

1. **Heartbeat** — every 100 ticks (5 seconds), log the current status. This is crucial for crash diagnosis — if the Pi dies, the last heartbeat timestamp tells us when.

2. **Watchdog** — if no `/cmd_vel` message has been received within `watchdog_timeout` (0.5s), stop the motors. This handles the case where teleop stops sending commands (e.g., you release the key, the teleop node crashes, or the network drops).

3. **Send command** — if the watchdog hasn't expired, convert the latest Twist to wheel speeds and send them.

### Shutdown

```python
def destroy_node(self):
    if self.serial_conn:
        try:
            self.stop_all_motors()
            self.get_logger().info('Motors stopped on shutdown.')
        except Exception as e:
            self.get_logger().error(f'Error stopping motors: {e}')
    super().destroy_node()
```

Stops all motors before the node exits. This overrides the base `destroy_node()` method.

### `main()`

```python
def main(args=None):
    rclpy.init(args=args)
    node = MotorDriverNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()
```

The `ExternalShutdownException` catch handles SIGTERM (e.g., from `kill` or `timeout`), which would otherwise cause an ugly traceback. The `rclpy.ok()` check prevents a double-shutdown error if ROS2 was already shut down externally.

## Safety Features

### Watchdog Timer

If no `/cmd_vel` message arrives for 0.5 seconds, the motors are stopped. This handles:
- Key release (teleop stops publishing)
- Teleop node crash
- Network disconnection

> [!warning] The RRC Lite has no watchdog
> If the **Pi itself** crashes, the RRC Lite keeps running the last motor command indefinitely. Our software watchdog can't help with this — it only works while the node is alive. This is a hardware limitation.

### Speed Clamping

Wheel speeds are clamped to `max_wheel_speed` (default 2.0 r/s) to prevent the robot from moving too fast during testing.

### Clean Shutdown

The `destroy_node()` override ensures motors are stopped even on ungraceful shutdown.

## Logging

The node uses the shared `NodeLogger` helper (see [[Logging-Setup]]) which writes to both the ROS2 `/rosout` topic and a human-readable file under `ros2_ws/runtime_logs`.

| Level | When | Example |
|-------|------|---------|
| INFO | Node startup | `MotorDriverNode starting. Port=/dev/ttyACM0...` |
| INFO | State transition (stopped → moving) | `Received movement command: v=0.41 m/s, ω=0.00 rad/s` |
| INFO | Heartbeat while moving | `Heartbeat: RUNNING, last_cmd=0.053s ago, v=0.41, ω=0.00` |
| DEBUG | Heartbeat while stopped | Same format, but suppressed at default `log_level` |
| DEBUG | Serial TX frame | `Serial TX: aa5503... speeds=[(0, 0.1), ...]` |
| WARN | Watchdog trigger | `Watchdog: no cmd_vel for 0.524s — stopping motors` |
| INFO | Shutdown | `Motors stopped on shutdown.` |

The heartbeat is the most important for crash diagnosis — if the Pi reboots, the last heartbeat timestamp in the log tells us exactly when it died.

Set `log_level:=debug` at launch to see every serial frame and cmd_vel message.

## Next Steps

- [[Differential-Drive-Kinematics]] — the math behind the speed conversion
- [[Motor-Mapping-Discovery]] — how we found the motor IDs and inversion
- [[Slice-3-Building-and-Testing]] — how to run it
- [[Slice-3-Overview]] — back to the slice overview
