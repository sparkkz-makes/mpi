# RRC Lite Communication Protocol

> Part of [[Slice-1-Overview]]. See also: [[Serial-Communication]], [[Protocol-Implementation]]

## Frame Format

Every message to and from the RRC Lite board uses this frame structure:

```
┌──────────┬──────────┬──────────────┬────────────┬──────────────┬──────────┐
│ 0xAA     │ 0x55     │ Function Code│ Data Length │ Parameters   │ Checksum │
│ (1 byte) │ (1 byte) │ (1 byte)     │ (1 byte)   │ (N bytes)    │ (1 byte) │
└──────────┴──────────┴──────────────┴────────────┴──────────────┴──────────┘
```

| Field | Size | Description |
|-------|------|-------------|
| **Frame Header** | 2 bytes | Always `0xAA 0x55` — marks the start of a frame |
| **Function Code** | 1 byte | What kind of command (buzzer, motor, LED, etc.) |
| **Data Length** | 1 byte | Number of bytes in the Parameters section |
| **Parameters** | Variable | Command-specific data (little-endian) |
| **Checksum** | 1 byte | CRC8 over Function Code + Data Length + Parameters |

## Byte Order: Little-Endian

All multi-byte values are **little-endian** (least significant byte first). For example:

- `100` (decimal) as `uint16` → `0x64 0x00`
- `1400` (decimal) as `uint16` → `0x78 0x05`
- `-1.0` (float) as `float32` → `0x00 0x00 0x80 0xBF`

This is why `struct.pack('<H', 1400)` produces `b'\x78\x05'` — the `<` means little-endian.

## The Checksum: CRC8 (Not a Simple Sum!)

> [!warning] The planning docs were misleading
> The master planning document described the checksum as:
> ```
> (Function + Length + sum(Parameters)) & 0xFF
> ```
> **This is wrong.** The actual RRC Lite firmware uses **CRC8** with polynomial 0x07. We discovered this by comparing our generated packet against the documented example.

### How We Verified

The protocol doc gives this example buzzer packet:

```
AA 55 02 08 78 05 64 00 64 00 05 00 F0
```

Breaking it down:
- Header: `AA 55`
- Function: `02` (buzzer)
- Length: `08` (8 bytes of parameters)
- Parameters: `78 05 64 00 64 00 05 00`
- Checksum: `F0`

Testing both methods:

| Method | Calculation | Result | Matches `F0`? |
|--------|-------------|--------|---------------|
| Simple sum | `(0x02 + 0x08 + 0x78 + 0x05 + 0x64 + 0x00 + 0x64 + 0x00 + 0x05 + 0x00) & 0xFF` | `0x54` | ❌ |
| CRC8 (poly 0x07) | Lookup table over `[0x02, 0x08, 0x78, 0x05, ...]` | `0xF0` | ✅ |

### CRC8 Algorithm

CRC8 with polynomial 0x07 uses a 256-byte lookup table. The algorithm:

```python
def calc_crc8(data: bytes) -> int:
    check = 0
    for byte in data:
        check = CRC8_TABLE[check ^ byte]
    return check & 0xFF
```

The table is precomputed from the polynomial `x⁸ + x² + x + 1` (0x07). See [[Protocol-Implementation]] for the full table and implementation.

The checksum is computed over **Function Code + Data Length + Parameters** (not the header bytes `AA 55`).

## Function Codes

| Code | Name | Purpose |
|------|------|---------|
| `0x00` | `FUNC_SYS` | System commands |
| `0x01` | `FUNC_LED` | LED control |
| `0x02` | `FUNC_BUZZER` | Buzzer control |
| `0x03` | `FUNC_MOTOR` | Motor control |
| `0x04` | `FUNC_PWM_SERVO` | PWM servo control |
| `0x05` | `FUNC_BUS_SERVO` | Serial bus servo control |
| `0x06` | `FUNC_KEY` | Key input |
| `0x07` | `FUNC_IMU` | IMU data |
| `0x08` | `FUNC_GAMEPAD` | Gamepad input |
| `0x09` | `FUNC_SBUS` | SBUS receiver |
| `0x0A` | `FUNC_OLED` | OLED display |
| `0x0B` | `FUNC_RGB` | RGB LED control |

## Buzzer Command (Function 0x02)

The buzzer command has 8 bytes of parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| Frequency | uint16 (Hz) | Sound frequency (e.g., 1400) |
| On duration | uint16 (ms) | How long to beep |
| Off duration | uint16 (ms) | Pause between beeps |
| Cycles | uint16 | Number of beep cycles |

### Example: 1400 Hz, 100ms on, 100ms off, 5 cycles

```
AA 55 02 08 78 05 64 00 64 00 05 00 F0
```

| Bytes | Meaning |
|-------|---------|
| `AA 55` | Frame header |
| `02` | Function: buzzer |
| `08` | Length: 8 bytes |
| `78 05` | Frequency: 1400 Hz (little-endian) |
| `64 00` | On time: 100 ms |
| `64 00` | Off time: 100 ms |
| `05 00` | Cycles: 5 |
| `F0` | CRC8 checksum |

## LED Command (Function 0x01)

Similar structure, 7 bytes of parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| LED ID | uint8 | Which LED (1-based) |
| On duration | uint16 (ms) | Light-on time |
| Off duration | uint16 (ms) | Light-off time |
| Cycles | uint16 | Number of blink cycles |

## Motor Command (Function 0x03)

Motor commands use a **subcommand** byte as the first parameter:

| Subcommand | Meaning |
|------------|---------|
| `0x00` | Control a single motor |
| `0x01` | Control multiple motors |
| `0x02` | Stop a single motor |
| `0x03` | Stop several motors (bitmask) |

### Single Motor (subcommand 0x00)

```
[0x00][motor_id: uint8][speed: float32]
```

Data length: 6 bytes (1 + 1 + 4)

Speed is a 4-byte IEEE 754 float in r/s. Negative = reverse.

### Multiple Motors (subcommand 0x01)

```
[0x01][count: uint8][motor_id_1: uint8][speed_1: float32][motor_id_2: uint8][speed_2: float32]...
```

Data length: 5N + 2 (where N = number of motors)

## PWM Servo Command (Function 0x04)

For the 2DOF gimbal servos. Uses subcommands:

| Subcommand | Meaning |
|------------|---------|
| `0x01` | Control several servos |
| `0x03` | Control a single servo |
| `0x05` | Read servo position |
| `0x07` | Set servo deviation |
| `0x09` | Read servo deviation |

Pulse width range: 500–2500 µs (corresponding to 0°–180°).

## Next Steps

- [[Protocol-Implementation]] — how all this is implemented in Python
- [[Serial-Communication]] — how the bytes get sent over the wire
- [[Slice-1-Overview]] — back to the slice overview
