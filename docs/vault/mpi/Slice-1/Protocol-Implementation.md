# Protocol Implementation: `protocol.py`

> Part of [[Slice-1-Overview]]. See also: [[RRC-Lite-Protocol]], [[ROS2-Python-Packages]]

This document walks through `mentorpi_driver/protocol.py` — the Python implementation of the RRC Lite serial protocol.

## File Location

```
ros2_ws/src/mentorpi_driver/mentorpi_driver/protocol.py
```

## Purpose

`protocol.py` is a **pure Python module** (not a ROS2 node). It provides the `RRCLiteProtocol` class that builds and parses serial frames. Other nodes import it to generate command packets:

```python
from .protocol import RRCLiteProtocol

cmd = RRCLiteProtocol.cmd_buzzer(1400, 100, 100, 5)
serial_conn.write(cmd)
```

This separation is intentional: the protocol logic has no ROS2 dependencies, so it can be tested independently and reused by any node.

## Structure Overview

```python
import struct

CRC8_TABLE = [...]  # 256-byte lookup table

class RRCLiteProtocol:
    FRAME_HEADER = bytes([0xAA, 0x55])

    # Function code constants
    FUNC_BUZZER = 2
    FUNC_MOTOR = 3
    ...

    # Subcommand constants
    MOTOR_CMD_SINGLE = 0x00
    ...

    @staticmethod
    def calc_crc8(data: bytes) -> int: ...

    @classmethod
    def pack_frame(cls, function_code, parameters) -> bytes: ...

    @classmethod
    def cmd_buzzer(cls, frequency_hz, on_time_ms, off_time_ms, cycles) -> bytes: ...
    ...
```

## The CRC8 Table

The CRC8 lookup table is precomputed from polynomial 0x07. It's a 256-element list where `CRC8_TABLE[i]` gives the CRC8 result for input byte `i` (starting from a check value of 0).

```python
CRC8_TABLE = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    # ... 256 entries total
]
```

> [!info] Why a lookup table?
> Computing CRC8 byte-by-byte with polynomial division is slow. The table precomputes all 256 possible results, so each byte is just one table lookup + XOR. This is a standard optimization for CRC.

## `calc_crc8` — The Checksum Function

```python
@staticmethod
def calc_crc8(data: bytes) -> int:
    """Compute CRC8 checksum using the RRC Lite lookup table."""
    check = 0
    for b in data:
        check = CRC8_TABLE[check ^ b]
    return check & 0xFF
```

How it works:
1. Start with `check = 0`
2. For each byte: XOR `check` with the byte, then look up the result in the table
3. The final `check` is the CRC8 value

The `& 0xFF` is a safety mask — the table values are already 0-255, but this guarantees the return type is a single byte.

## `pack_frame` — Building a Frame

This is the core method that all command builders use:

```python
@classmethod
def pack_frame(cls, function_code: int, parameters: bytes) -> bytes:
    data_length = len(parameters)
    # CRC8 is computed over [Func][Len][Params]
    crc_data = bytes([function_code, data_length]) + parameters
    checksum = cls.calc_crc8(crc_data)

    frame = bytearray(cls.FRAME_HEADER)  # AA 55
    frame.append(function_code)           # Func
    frame.append(data_length)            # Len
    frame.extend(parameters)             # Params
    frame.append(checksum)               # CRC8

    return bytes(frame)
```

Step by step:
1. Calculate the data length (number of parameter bytes)
2. Compute CRC8 over `[function_code, data_length] + parameters` — note the header (`AA 55`) is **not** included in the checksum
3. Build the frame: header → function → length → parameters → checksum
4. Return as immutable `bytes`

## `cmd_buzzer` — Buzzer Command

```python
@classmethod
def cmd_buzzer(cls, frequency_hz: int, on_time_ms: int,
               off_time_ms: int, cycles: int) -> bytes:
    params = struct.pack('<HHHH', frequency_hz, on_time_ms,
                         off_time_ms, cycles)
    return cls.pack_frame(cls.FUNC_BUZZER, params)
```

`struct.pack('<HHHH', ...)` packs four unsigned 16-bit integers in little-endian order:
- `<` = little-endian
- `H` = unsigned 16-bit integer
- Four `H`s = four uint16 values

So `struct.pack('<HHHH', 1400, 100, 100, 5)` produces `b'\x78\x05\x64\x00\x64\x00\x05\x00'` — exactly the 8 parameter bytes from the protocol doc.

## `cmd_led` — LED Command

```python
@classmethod
def cmd_led(cls, led_id: int, on_time_ms: int, off_time_ms: int,
            cycles: int) -> bytes:
    params = struct.pack('<BHHH', led_id, on_time_ms, off_time_ms, cycles)
    return cls.pack_frame(cls.FUNC_LED, params)
```

Same pattern, but the first parameter is a `uint8` (`B` in struct format) for the LED ID, followed by three `uint16` values.

## `cmd_motor_single` — Single Motor Command

```python
@classmethod
def cmd_motor_single(cls, motor_id: int, speed: float) -> bytes:
    params = struct.pack('<BBf', cls.MOTOR_CMD_SINGLE, motor_id, speed)
    return cls.pack_frame(cls.FUNC_MOTOR, params)
```

Format: `<BBf` = uint8 (subcommand) + uint8 (motor ID) + float32 (speed). The float is 4 bytes, so total parameters = 6 bytes, matching the protocol's data length of 6.

## `cmd_motor_multiple` — Multi-Motor Command

```python
@classmethod
def cmd_motor_multiple(cls, motor_data: list) -> bytes:
    count = len(motor_data)
    params = bytearray([cls.MOTOR_CMD_MULTIPLE, count])
    for motor_id, speed in motor_data:
        params.append(motor_id)
        params.extend(struct.pack('<f', speed))
    return cls.pack_frame(cls.FUNC_MOTOR, bytes(params))
```

This one is more complex because the number of motors is variable. It uses a `bytearray` (mutable) and extends it in a loop. Each motor contributes 1 byte (ID) + 4 bytes (float speed) = 5 bytes, so total length = 2 + 5N.

## `cmd_motor_stop_single` and `cmd_motor_stop_several`

```python
@classmethod
def cmd_motor_stop_single(cls, motor_id: int) -> bytes:
    params = struct.pack('<BB', cls.MOTOR_CMD_STOP_SINGLE, motor_id)
    return cls.pack_frame(cls.FUNC_MOTOR, params)

@classmethod
def cmd_motor_stop_several(cls, motor_mask: int) -> bytes:
    params = struct.pack('<BB', cls.MOTOR_CMD_STOP_SEVERAL, motor_mask)
    return cls.pack_frame(cls.FUNC_MOTOR, params)
```

The "stop several" command uses a **bitmask**: bit 0 = motor 1, bit 1 = motor 2, etc. So `0x05` (binary `00000101`) stops motors 1 and 3.

## PWM Servo Commands

```python
@classmethod
def cmd_pwm_servo_single(cls, servo_id: int, pulse_width: int,
                         motion_time_ms: int) -> bytes:
    params = struct.pack('<BHB', cls.PWM_SERVO_CMD_SINGLE,
                         motion_time_ms, servo_id)
    params += struct.pack('<H', pulse_width)
    return cls.pack_frame(cls.FUNC_PWM_SERVO, params)
```

Note the parameter order: subcommand → motion time → servo ID → pulse width. This matches the protocol doc exactly. The `+=` concatenates the pulse width as a separate `struct.pack` call (could also be done in one pack with `'<BHBBH'`... actually `'<BHBBH'` would be wrong due to padding — see the note below).

> [!note] struct padding
> Python's `struct` module doesn't add padding by default when using `<` (little-endian), so `struct.pack('<BHB', ...)` produces exactly 4 bytes. But mixing sizes can be tricky, which is why the code splits it into two `struct.pack` calls for clarity.

## Design Patterns Used

### Classmethod + Class Variables
All methods are `@classmethod` and constants are class variables. This means you don't need to instantiate `RRCLiteProtocol` — you just call the methods directly:

```python
RRCLiteProtocol.cmd_buzzer(1400, 100, 100, 5)
```

This is appropriate because the protocol is stateless — it's just a set of pure functions for building byte sequences.

### Separation of Concerns
`protocol.py` knows nothing about ROS2, serial ports, or hardware. It only builds and parses byte sequences. This makes it:
- **Testable** — you can unit test packet generation without hardware
- **Reusable** — any node can import it
- **Portable** — could be used outside ROS2 if needed

## Next Steps

- [[Buzzer-Node-Walkthrough]] — see how `protocol.py` is used in a real node
- [[Serial-Driver-Node-Walkthrough]] — another usage example
- [[RRC-Lite-Protocol]] — the protocol specification this implements
