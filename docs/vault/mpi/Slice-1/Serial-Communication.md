# Serial Communication with the RRC Lite

> Part of [[Slice-1-Overview]]. See also: [[RRC-Lite-Protocol]], [[ROS2-Parameters]]

## The Connection

The RRC Lite board communicates with the Raspberry Pi over **UART** (Universal Asynchronous Receiver-Transmitter). On the Pi, this appears as a serial port device file in `/dev/`.

### Finding the Serial Port

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

On our setup, the RRC Lite shows up as `/dev/ttyACM0` (USB CDC class — it has a built-in USB-to-serial converter). If you're using a separate USB-to-TTL adapter, it might appear as `/dev/ttyUSB0` instead.

> [!tip] Can't find the port?
> - Make sure the RRC Lite is powered on and the USB cable is connected
> - Run `dmesg | tail` after plugging in to see what device was assigned
> - Check permissions: `sudo usermod -aG dialout $USER` then log out and back in

## Using pyserial

We use the [pyserial](https://pyserial.readthedocs.io/) library to talk to the serial port. It's a pure-Python serial port wrapper.

### Opening a Connection

```python
import serial

ser = serial.Serial(
    port='/dev/ttyACM0',
    baudrate=1000000,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.02,  # 20ms read timeout
)
```

| Parameter | Value | Why |
|-----------|-------|-----|
| `port` | `/dev/ttyACM0` | Where the RRC Lite appears |
| `baudrate` | `1000000` | 1 Mbps — the RRC Lite's fixed rate |
| `bytesize` | `EIGHTBITS` | 8 data bits per byte |
| `parity` | `PARITY_NONE` | No parity bit |
| `stopbits` | `STOPBITS_ONE` | 1 stop bit |
| `timeout` | `0.02` | 20ms read timeout — non-blocking reads |

### Why 1 Mbps?

The RRC Lite firmware is configured for 1,000,000 bps. This is unusually fast for serial, but it's necessary because the board sends a lot of real-time data (encoder feedback, IMU readings) and we need low latency for motor control.

> [!warning] A bug from our earlier attempt
> The first version of this project (in a different workspace) used 115200 baud. The buzzer never sounded because the board couldn't understand the garbled data. Always match the hardware's expected baud rate.

### Sending Data

```python
frame = b'\xAA\x55\x02\x08\x78\x05\x64\x00\x64\x00\x05\x00\xF0'
ser.write(frame)
```

`write()` sends raw bytes. The `bytes` type in Python is perfect for this — each element is a byte (0-255).

### Reading Data (for later slices)

```python
data = ser.read(64)  # Read up to 64 bytes (with 20ms timeout)
```

We don't need to read anything in Slice 1 (the buzzer is fire-and-forget), but later slices will read encoder feedback and IMU data.

### Closing the Connection

```python
ser.close()
```

Or use a context manager:

```python
with serial.Serial('/dev/ttyACM0', 1000000) as ser:
    ser.write(frame)
# Automatically closed when the block exits
```

## Serial in ROS2 Nodes

In our project, each node that needs serial access opens its own connection. This is fine for Slice 1 where only one node runs at a time, but in later slices we'll centralize serial access in the `serial_driver` node and have other nodes communicate via ROS2 topics.

See [[Serial-Driver-Node-Walkthrough]] for how the serial driver node manages the connection, and [[Buzzer-Node-Walkthrough]] for how the buzzer node uses it directly.

## Common Issues

### "Permission denied" on `/dev/ttyACM0`
Your user isn't in the `dialout` group:
```bash
sudo usermod -aG dialout $USER
# Log out and back in (or reboot)
```

### "Device or resource busy"
Another process has the port open. Serial ports can only be opened by one process at a time. Kill any other nodes that might be using it:
```bash
ps aux | grep serial
```

### Data seems garbled
Most likely a baud rate mismatch. Double-check you're using 1000000.

## Next Steps

- [[RRC-Lite-Protocol]] — what bytes to send over the serial connection
- [[Protocol-Implementation]] — the Python code that builds those bytes
- [[Buzzer-Node-Walkthrough]] — a complete node using serial
