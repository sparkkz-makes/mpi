# Differential Drive Kinematics

> Part of [[Slice-3-Overview]]. See also: [[Motor-Driver-Node-Walkthrough]], [[RRC-Lite-Protocol]]

## What Is Differential Drive?

A differential drive robot has left and right wheels that can spin independently. By driving the left and right wheels at different speeds, the robot can turn. This is the simplest model that works for our 4-wheel skid-steer chassis.

```
     Front
  ┌────────┐
  │ FL  FR │   ← Left and right pairs spin at different speeds
  │        │
  │ RL  RR │   ← Rear wheels follow the same speed as their front pair
  └────────┘
     Back
```

> [!note] This is a simplification
> Our robot has Mecanum wheels that can strafe (move sideways), but for Slice 3 we're using a simple differential drive model. Full Mecanum kinematics comes in [[Slice-5-Overview]].

## The Math

Given a Twist message with:
- $v$ = `linear.x` (forward velocity in m/s)
- $\omega$ = `angular.z` (rotation rate in rad/s)

The velocity of each side of the robot is:

$$v_{left} = v - \omega \cdot \frac{W}{2}$$

$$v_{right} = v + \omega \cdot \frac{W}{2}$$

Where $W$ is the **track width** (distance between left and right wheels, in metres).

### Intuition

- When going straight forward ($\omega = 0$): both sides get $v$ — equal speed
- When turning left ($\omega > 0$): left side slows, right side speeds up
- When turning in place ($v = 0$): left goes backward, right goes forward

### Converting to Wheel Speed (r/s)

The RRC Lite expects motor speeds in **revolutions per second** (r/s), not m/s. We convert using the wheel circumference:

$$\text{rps} = \frac{v_{side}}{2\pi r}$$

Where $r$ is the **wheel radius** in metres.

## Our Robot's Values

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `wheel_radius` | 0.0325 m | ~65mm diameter wheels |
| `track_width` | 0.10 m | 10cm between left/right wheels |
| `max_wheel_speed` | 2.0 r/s | Safety clamp |

Wheel circumference = $2\pi \times 0.0325 \approx 0.204$ m

So at max speed (2.0 r/s), the robot moves at $2.0 \times 0.204 \approx 0.41$ m/s.

## Example Calculations

### Forward at 0.5 m/s

$$v_{left} = 0.5 - 0 = 0.5 \text{ m/s}$$
$$v_{right} = 0.5 + 0 = 0.5 \text{ m/s}$$
$$\text{rps}_{left} = \frac{0.5}{0.204} \approx 2.45 \text{ r/s}$$

Both sides equal — robot goes straight. (Clamped to 2.0 r/s by max_wheel_speed.)

### Turn left at 1.0 rad/s

$$v_{left} = 0 - 1.0 \times 0.05 = -0.05 \text{ m/s}$$
$$v_{right} = 0 + 1.0 \times 0.05 = 0.05 \text{ m/s}$$
$$\text{rps}_{left} \approx -0.24 \text{ r/s}$$
$$\text{rps}_{right} \approx 0.24 \text{ r/s}$$

Left wheels reverse, right wheels forward — robot spins left in place.

### Forward + turn right (0.5 m/s, -1.0 rad/s)

$$v_{left} = 0.5 - (-1.0) \times 0.05 = 0.55 \text{ m/s}$$
$$v_{right} = 0.5 + (-1.0) \times 0.05 = 0.45 \text{ m/s}$$

Left side faster than right — robot curves to the right while moving forward.

## Motor Inversion

The math gives us the **desired** wheel speed, but the physical motor direction depends on how the motor is mounted. On our robot:

- Front Left (ID 0) and Rear Left (ID 1) motors are mounted such that positive speed = **backward**
- Front Right (ID 2) and Rear Right (ID 3) motors are mounted such that positive speed = **forward**

So we invert the left-side motors by negating their speed:

```python
if invert:
    speed = -speed
```

This ensures that positive `linear.x` = forward on all wheels. See [[Motor-Mapping-Discovery]] for how we figured this out.

## In the Code

```python
def twist_to_wheel_speeds(self, twist: Twist):
    v = twist.linear.x
    omega = twist.angular.z

    v_left = v - omega * self.track_width / 2.0
    v_right = v + omega * self.track_width / 2.0

    circumference = 2.0 * math.pi * self.wheel_radius
    rps_left = v_left / circumference
    rps_right = v_right / circumference

    # Clamp to safe maximum
    rps_left = max(-self.max_wheel_speed,
                   min(self.max_wheel_speed, rps_left))
    rps_right = max(-self.max_wheel_speed,
                    min(self.max_wheel_speed, rps_right))

    # Apply per-motor inversion
    raw_speeds = [rps_left, rps_right, rps_left, rps_right]  # FL, FR, RL, RR
    wheel_speeds = []
    for motor_id, speed, invert in zip(
        self.motor_ids, raw_speeds, self.invert_motors
    ):
        if invert:
            speed = -speed
        wheel_speeds.append((motor_id, speed))

    return wheel_speeds
```

## Limitations

This differential drive model only supports:
- ✅ Forward/backward (`linear.x`)
- ✅ Turning left/right (`angular.z`)
- ❌ Strafing left/right (`linear.y`) — requires Mecanum kinematics

When `linear.y` is non-zero (e.g., pressing shift+keys in teleop), it's simply ignored. Full Mecanum support comes in [[Slice-5-Overview]].

## Next Steps

- [[Motor-Driver-Node-Walkthrough]] — see this math in the full node context
- [[Motor-Mapping-Discovery]] — how we found which motor is which
- [[Slice-5-Overview]] — full Mecanum kinematics (not yet written)
