# Motor Mapping Discovery

> Part of [[Slice-3-Overview]]. See also: [[Motor-Driver-Node-Walkthrough]], [[RRC-Lite-Protocol]]

## The Problem

The RRC Lite protocol documentation shows motor IDs 1-4 in its examples:

```
Control motor 1 to rotate at -1 r/s:
AA5503060001000080BFDA
```

But when we sent commands to motor ID 4, **the board crashed** and required a power cycle to recover. We needed to figure out the correct motor IDs and which direction each motor spins.

## Discovery Process

### Step 1: Verify the Protocol

First, we confirmed our packet generation matched the documented example:

```python
documented = bytes.fromhex('AA5503060001000080BFDA')
our_cmd = RRCLiteProtocol.cmd_motor_single(1, -1.0)
# Match: True ✅
```

The protocol implementation was correct — the issue was with the motor IDs.

### Step 2: Test Motor ID 0

Since IDs 1-3 worked but 4 crashed the board, we hypothesized the firmware uses **0-indexed** IDs (0-3) instead of 1-indexed (1-4).

After a power cycle, we tested motor ID 0:

```python
cmd = RRCLiteProtocol.cmd_motor_single(0, 1.0)
ser.write(cmd)
```

**Motor 0 moved!** This confirmed the firmware uses IDs 0-3.

### Step 3: Sequential Spin Test

To map each motor ID to its physical wheel position, we spun each motor one at a time for 3 seconds and observed which wheel turned:

```python
for motor_id in range(4):
    cmd = RRCLiteProtocol.cmd_motor_single(motor_id, 1.0)
    ser.write(cmd)
    time.sleep(3)
    ser.write(RRCLiteProtocol.cmd_motor_stop_single(motor_id))
    time.sleep(1)
```

### Results

| Motor ID | Physical Position | Direction at +1.0 r/s |
|----------|------------------|----------------------|
| 0 | Front Left | Clockwise (backward) |
| 1 | Rear Left | Counter-clockwise (backward) |
| 2 | Front Right | Counter-clockwise (forward) |
| 3 | Rear Right | Clockwise (forward) |

### Step 4: Determine Inversion

For positive speed = forward on all wheels, we need to invert the motors that spin backward at positive speed:

- Front Left (ID 0): backward → **invert**
- Rear Left (ID 1): backward → **invert**
- Front Right (ID 2): forward → ok
- Rear Right (ID 3): forward → ok

### Step 5: Verify All-Forward

We tested all four motors with the inversion applied:

```python
cmd = RRCLiteProtocol.cmd_motor_multiple([
    (0, -1.0),  # FL - inverted
    (2, 1.0),   # FR
    (1, -1.0),  # RL - inverted
    (3, 1.0),   # RR
])
ser.write(cmd)
```

**All four wheels drove forward!** ✅

## Final Configuration

In `motor_driver.py`:

```python
# motor_ids ordered as [FL, FR, RL, RR]
self.declare_parameter('motor_ids', [0, 2, 1, 3])

# Invert motors that spin backward at positive speed
self.declare_parameter('invert_motors', [True, False, True, False])
```

The `motor_ids` list is ordered as **[Front-Left, Front-Right, Rear-Left, Rear-Right]** because that's the convention used in the kinematics math. The actual firmware IDs are remapped through this list.

## Lessons Learned

1. **Don't trust the docs blindly** — the protocol doc showed IDs 1-4, but the firmware used 0-3. Always verify with hardware.

2. **Invalid IDs can crash the board** — sending motor ID 4 caused the RRC Lite to become unresponsive, requiring a power cycle. This is a significant finding for safety.

3. **Sequential testing is powerful** — spinning one motor at a time made it easy to identify which ID maps to which wheel and which direction it spins.

4. **Motor mounting affects direction** — motors on the same side of the chassis are physically mirrored, so they need software inversion to produce consistent forward motion.

## Next Steps

- [[Motor-Driver-Node-Walkthrough]] — how this configuration is used in the node
- [[Differential-Drive-Kinematics]] — the math that uses these motor IDs
- [[Slice-3-Overview]] — back to the slice overview
