# Logging Setup & Usage

> How logging works in the `mentorpi_driver` package and how to use it.

## Why We Have Two Log Outputs

Every driver node uses both:

1. **rclpy logger** — integrates with ROS2 (`/rosout`, `ros2 topic echo /rosout`, RViz, bag files).
2. **File logger** — developer-friendly local log files with human-readable timestamps.

This gives us the best of both worlds: ROS2 tooling works, and we get readable per-run logs.

## File Logger Details

- Powered by [loguru](https://github.com/Delgan/loguru).
- Writes to `ros2_ws/runtime_logs/<node_name>_YYYY-MM-DD_HH-MM-SS.log`.
- Keeps the last 10 log files automatically.
- Format: `2026-07-19 02:38:24.802 | INFO | module:function:line | message`.

## How to Use in a Node

```python
from .logging_utils import NodeLogger

class MyNode(Node):
    def __init__(self):
        super().__init__('my_node')
        self.declare_parameter('log_level', 'info')
        self.log = NodeLogger(self, level=self.get_parameter('log_level').value)

        self.log.info('Node started')
        self.log.debug('Verbose diagnostic')
```

## Log Levels

Valid levels: `debug`, `info`, `warn`, `error`, `fatal`.

Set at launch:

```bash
ros2 run mentorpi_driver motor_driver --ros-args -p log_level:=debug
```

## Current Logging Behaviour in `motor_driver`

| Event | Level | Notes |
|-------|-------|-------|
| Node startup | INFO | Port, baud, geometry, motor IDs |
| Serial open/close | INFO / ERROR | |
| Movement command received | INFO | Only on stopped → moving transition |
| cmd_vel details | DEBUG | Every message |
| Serial TX frame | DEBUG | Hex + decoded speeds |
| Heartbeat | INFO when moving, DEBUG when stopped | Every 5s |
| Watchdog trigger | WARN | Only on first trigger |
| Shutdown | INFO / ERROR | Motors stopped |

## Build & Run Workflow

```bash
cd /home/stu/dev/mpi/ros2_ws

# Build (and optionally activate)
./build.sh
# or
source build.sh

# Activate manually if you didn't source build.sh
source activate.sh

# Run a node
ros2 run mentorpi_driver motor_driver --ros-args -p log_level:=debug
```

## Installing Extra Python Packages

Use the workspace venv:

```bash
source /home/stu/dev/mpi/.venv/bin/activate
uv pip install <package>
```

See also: [[Workspace-Python-Environment]]
