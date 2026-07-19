# ROS2 Parameters

> Part of the [[ROS2-How-To]] series. See also: [[ROS2-Nodes-and-Topics]], [[Buzzer-Node-Walkthrough]]

## What Are Parameters?

**Parameters** are configurable values on a node — like settings or options. They let you change a node's behavior without editing code. You set them from the command line, launch files, or other nodes.

In our project, the serial port and baud rate are parameters:

```bash
ros2 run mentorpi_driver buzzer_node --ros-args -p port:=/dev/ttyUSB0
```

## Declaring Parameters

In Python, use `declare_parameter` inside the node's `__init__`:

```python
class BuzzerNode(Node):
    def __init__(self):
        super().__init__('buzzer_node')

        # Declare with a default value
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)

        # Read the value
        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
```

Key points:
- The first argument is the **parameter name** (a string)
- The second is the **default value** — its Python type determines the parameter type (string, int, float, bool, etc.)
- `get_parameter('name').value` retrieves the current value
- If you don't declare a parameter and someone tries to set it, ROS2 will throw an error

## Setting Parameters from the Command Line

Use `--ros-args -p name:=value`:

```bash
# String parameter
ros2 run mentorpi_driver buzzer_node --ros-args -p port:=/dev/ttyUSB0

# Integer parameter
ros2 run mentorpi_driver buzzer_node --ros-args -p baudrate:=115200

# Multiple parameters
ros2 run mentorpi_driver buzzer_node \
    --ros-args \
    -p port:=/dev/ttyUSB0 \
    -p baudrate:=115200
```

### Type Coercion

ROS2 tries to infer the type from the default value you declared. If you declared `baudrate` as `1000000` (int), passing `-p baudrate:=500000` works. But passing `-p baudrate:=fast` will fail because it can't convert a string to int.

## Inspecting Parameters at Runtime

```bash
# List all parameters on a node
ros2 param list /buzzer_node

# Get a specific parameter's value
ros2 param get /buzzer_node port

# Set a parameter on a running node
ros2 param set /buzzer_node baudrate 115200
```

## Parameter Types

The type is inferred from the default value:

| Python Default | ROS2 Type |
|----------------|-----------|
| `'hello'` | string |
| `42` | integer |
| `3.14` | double (float) |
| `True` | boolean |
| `['a', 'b']` | string array |
| `[1, 2, 3]` | integer array |

## Describing Parameters (Optional but Good Practice)

For better documentation and validation, you can declare parameters with descriptions:

```python
from rcl_interfaces.msg import ParameterDescriptor, FloatingPointRange

self.declare_parameter(
    'baudrate',
    1000000,
    ParameterDescriptor(
        description='Serial baud rate for the RRC Lite board',
        integer_range=[IntegerRange(from_value=9600, to_value=4000000)]
    )
)
```

This enables type checking and range validation, and shows up in `ros2 param describe`.

## Why We Use Parameters

In our `buzzer_node` and `serial_driver`, the serial port is a parameter because:

1. **Different hardware setups** — the RRC Lite might appear as `/dev/ttyACM0`, `/dev/ttyUSB0`, or something else depending on the USB adapter
2. **Testing** — you might want to point at a virtual serial port for testing
3. **No code changes needed** — just pass a different value at runtime

This is a core ROS2 design principle: **make hardware-specific values configurable, not hardcoded**.

## Next Steps

- [[ROS2-Running-Nodes]] — passing parameters when running nodes
- [[Buzzer-Node-Walkthrough]] — see parameters in the buzzer node
- [[Serial-Driver-Node-Walkthrough]] — parameters in the serial driver
