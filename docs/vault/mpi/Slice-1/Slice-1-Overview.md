# Slice 1: Base System & Serial Communication

> Part of the [[Project-Overview]]. See also: [[ROS2-Workspace-Setup]], [[ROS2-Python-Packages]]

## Objective

Establish a functional ROS2 environment on the Raspberry Pi and verify low-level communication with the RRC Lite board by triggering an audible buzzer response.

This is the foundation — if we can make the buzzer sound, we've proven the entire serial communication chain works:

```
ROS2 node → protocol.py (CRC8 frame) → pyserial → RRC Lite → buzzer
```

## What We Built

### Package: `mentorpi_driver`

A ROS2 Python package containing three files:

| File | Purpose |
|------|---------|
| `protocol.py` | Implements the RRC Lite serial protocol — builds and parses frames |
| `serial_driver.py` | ROS2 node that manages the serial connection, subscribes to `test_led` topic |
| `buzzer_node.py` | ROS2 node that beeps the buzzer every 5 seconds (proof-of-life test) |

### Detailed Walkthroughs

- [[Serial-Communication]] — how pyserial connects to the RRC Lite board
- [[RRC-Lite-Protocol]] — the frame format and CRC8 checksum explained
- [[Protocol-Implementation]] — line-by-line walkthrough of `protocol.py`
- [[Buzzer-Node-Walkthrough]] — line-by-line walkthrough of `buzzer_node.py`
- [[Serial-Driver-Node-Walkthrough]] — line-by-line walkthrough of `serial_driver.py`
- [[Building-and-Testing]] — how to build, run, and verify the buzzer

## Technical Details

### Serial Connection

| Setting | Value |
|---------|-------|
| **Port** | `/dev/ttyACM0` (default, configurable via parameter) |
| **Baud rate** | 1,000,000 bps (1 Mbps) |
| **Data bits** | 8 |
| **Parity** | None |
| **Stop bits** | 1 |

### Buzzer Command

The buzzer command uses function code `0x02` with 8 bytes of parameters:

| Parameter | Type | Example |
|-----------|------|---------|
| Frequency | uint16 (Hz) | 1400 Hz |
| On duration | uint16 (ms) | 100 ms |
| Off duration | uint16 (ms) | 100 ms |
| Cycles | uint16 | 5 |

Example packet: `AA 55 02 08 78 05 64 00 64 00 05 00 F0`

See [[RRC-Lite-Protocol]] for how this packet is constructed.

## Verification

The buzzer was confirmed to sound when running:

```bash
ros2 run mentorpi_driver buzzer_node
```

The node beeps every 5 seconds (1400 Hz, 100ms on, 100ms off, 2 cycles). Press `Ctrl+C` to stop — the node sends a stop command on shutdown to silence the buzzer.

> [!note] A bug we found and fixed
> The buzzer kept sounding after `Ctrl+C` because there was no shutdown handler. We added a `finally` block that sends a buzzer-stop command (0 Hz, 0 cycles) before the node exits. See [[Buzzer-Node-Walkthrough]] for details.

## What We Learned

1. **The RRC Lite uses CRC8, not a simple sum** — the master planning doc described the checksum as `(Func + Len + sum(Payload)) & 0xFF`, but the actual firmware uses CRC8 with polynomial 0x07. We verified this by comparing our generated packet against the documented example (`F0` checksum). See [[RRC-Lite-Protocol]].

2. **Serial port naming** — the RRC Lite appears as `/dev/ttyACM0` on our Pi (USB CDC). It could also appear as `/dev/ttyUSB0` depending on the adapter. Making it a ROS2 parameter lets us change it without recompiling.

3. **Clean shutdown matters** — hardware devices don't automatically stop when your program exits. You need to explicitly send stop commands.

## Next Steps

With Slice 1 complete, we have a working serial communication foundation. The next slice is [[Slice-2-Overview]] (PC Teleoperation), where we'll publish `geometry_msgs/Twist` messages from a keyboard to the `/cmd_vel` topic.