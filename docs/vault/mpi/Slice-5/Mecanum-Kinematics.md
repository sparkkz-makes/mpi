# Mecanum Kinematics

> Part of [[Slice-5-Overview]]. See also: [[Differential-Drive-Kinematics]], [[Motor-Mapping-Discovery]], [[RRC-Lite-Protocol]]

## Why Mecanum?

A standard wheel only rolls in the direction it points. A **Mecanum wheel** has rollers mounted at 45° around its rim, so the wheel can also slide sideways. With four Mecanum wheels arranged in an **X-pattern** (also called ABAB), the robot can move in any direction without turning first — forward, backward, strafe left/right, and any diagonal, all while also rotating.

## The X-Pattern

The rollers on the four wheels form an X when viewed from above:

```
     Front
  ┌──────────┐
  │ FL ╲ ╱ FR │   FL roller points ↖ (toward front-left)
  │     ╳     │   FR roller points ↗ (toward front-right)
  │ RL ╱ ╲ RR │   RL roller points ↙ (toward rear-left)
  │           │   RR roller points ↘ (toward rear-right)
  └──────────┘
     Back
```

This is the **ABAB** pattern: A-type wheels (FL, RR) have rollers pointing one way, B-type wheels (FR, RL) have rollers pointing the other way. The diagonal pairs (FL+RR and FR+RL) are the same type.

> [!warning] Pattern matters
> If the wheels are installed in the wrong pattern (e.g. all rollers pointing the same way, or an O-pattern instead of X), strafing will produce unexpected motion or no motion at all. The MentorPi ships with the correct X-pattern.

## The Math

### Inputs

A `geometry_msgs/Twist` message gives us three velocities in the robot's frame:

| Symbol | Twist field | Meaning | Sign convention |
|--------|-------------|---------|-----------------|
| $v_x$ | `linear.x` | Forward velocity | + = forward |
| $v_y$ | `linear.y` | Strafe velocity | + = left (ROS REP-103) |
| $\omega$ | `angular.z` | Rotation rate | + = counter-clockwise (CCW) |

### Geometry

| Symbol | Parameter | Meaning |
|--------|-----------|---------|
| $r$ | `wheel_radius` | Wheel radius (m) |
| $W$ | `track_width` | Left-to-right wheel centre distance (m) |
| $L$ | `wheel_base` | Front-to-back wheel centre distance (m) |

Define the **half-diagonal** from the chassis centre to a wheel:

$$K = \frac{L + W}{2} = l + w$$

where $l = L/2$ and $w = W/2$. This is the moment arm for rotation — the distance from the chassis centre to the wheel contact point projected onto the direction of motion.

### Inverse Kinematics (Twist → Wheel Speeds)

The linear velocity at each wheel's contact point (in m/s):

$$v_{FL} = v_x - v_y - \omega \cdot K$$
$$v_{FR} = v_x + v_y + \omega \cdot K$$
$$v_{RL} = v_x + v_y - \omega \cdot K$$
$$v_{RR} = v_x - v_y + \omega \cdot K$$

### Convert to Revolutions per Second

The RRC Lite expects motor speeds in **r/s**, not m/s. Convert using the wheel circumference:

$$\text{rps}_i = \frac{v_i}{2\pi r}$$

### Why These Signs?

The signs come from the roller angles. For an X-pattern:

- **Strafe left** ($v_y > 0$): FL and RR wheels must drive **backward** (their rollers push the robot left), while FR and RL drive **forward**. Hence $-v_y$ for FL & RR, $+v_y$ for FR & RL.
- **Turn CCW** ($\omega > 0$): left wheels go backward, right wheels go forward. FL & RL get $-\omega K$, FR & RR get $+\omega K$.
- **Forward** ($v_x > 0$): all wheels get $+v_x$.

Summing these three contributions gives the equations above. Because the sum is **linear**, all three motions combine independently — this is what makes compound motions (diagonal drive, curved strafe) work for free.

## Worked Examples

Using our robot's values: $r = 0.0325$ m, $W = 0.10$ m, $L = 0.10$ m, so $K = 0.10$ m and circumference $\approx 0.204$ m.

### 1. Pure strafe left (0.3 m/s, no forward, no turn)

$$v_{FL} = 0 - 0.3 - 0 = -0.3 \text{ m/s}$$
$$v_{FR} = 0 + 0.3 + 0 = +0.3 \text{ m/s}$$
$$v_{RL} = 0 + 0.3 - 0 = +0.3 \text{ m/s}$$
$$v_{RR} = 0 - 0.3 + 0 = -0.3 \text{ m/s}$$

FL & RR backward, FR & RL forward → robot slides left. ✅

### 2. 45° forward-right diagonal (0.3 m/s forward, -0.3 m/s strafe)

$$v_{FL} = 0.3 - (-0.3) - 0 = +0.6 \text{ m/s}$$
$$v_{FR} = 0.3 + (-0.3) + 0 = 0 \text{ m/s}$$
$$v_{RL} = 0.3 + (-0.3) - 0 = 0 \text{ m/s}$$
$$v_{RR} = 0.3 - (-0.3) + 0 = +0.6 \text{ m/s}$$

Only the FL & RR wheels drive (the diagonal pair) → robot moves diagonally forward-right. ✅

### 3. Turn in place CCW (1.0 rad/s)

$$v_{FL} = 0 - 0 - 1.0 \times 0.10 = -0.10 \text{ m/s}$$
$$v_{FR} = 0 + 0 + 1.0 \times 0.10 = +0.10 \text{ m/s}$$
$$v_{RL} = 0 + 0 - 1.0 \times 0.10 = -0.10 \text{ m/s}$$
$$v_{RR} = 0 - 0 + 1.0 \times 0.10 = +0.10 \text{ m/s}$$

Left wheels backward, right wheels forward → spins CCW. ✅ (Same as differential drive for pure rotation.)

### 4. Forward + strafe + turn (compound)

$v_x = 0.3$, $v_y = 0.2$, $\omega = 0.5$:

$$v_{FL} = 0.3 - 0.2 - 0.5 \times 0.10 = +0.05 \text{ m/s}$$
$$v_{FR} = 0.3 + 0.2 + 0.5 \times 0.10 = +0.55 \text{ m/s}$$
$$v_{RL} = 0.3 + 0.2 - 0.5 \times 0.10 = +0.45 \text{ m/s}$$
$$v_{RR} = 0.3 - 0.2 + 0.5 \times 0.10 = +0.15 \text{ m/s}$$

All four wheels at different speeds — the robot drives forward, drifts left, and slowly rotates CCW all at once.

## Motor Inversion

The kinematic equations give the **desired** wheel velocity in the robot frame. The physical motor direction depends on how each motor is mounted. On the MentorPi, the left-side motors (FL id 0, RL id 1) spin backward at positive speed, so they are inverted in software:

```python
if invert:
    speed = -speed
```

See [[Motor-Mapping-Discovery]] for how this was determined. The inversion is applied **after** the kinematics, so the equations above are written in the standard robot frame and remain readable.

## In the Code

```python
# Pre-computed in __init__:
self._kinematic_K = (self.wheel_base + self.track_width) / 2.0

def twist_to_wheel_speeds(self, twist: Twist):
    v_x = twist.linear.x          # forward
    v_y = twist.linear.y          # strafe left (REP-103)
    omega = twist.angular.z       # turn CCW
    K = self._kinematic_K

    v_fl = v_x - v_y - omega * K
    v_fr = v_x + v_y + omega * K
    v_rl = v_x + v_y - omega * K
    v_rr = v_x - v_y + omega * K

    circumference = 2.0 * math.pi * self.wheel_radius
    raw_speeds = [v_fl, v_fr, v_rl, v_rr]  # in m/s
    # ... clamp, invert, return as (motor_id, rps) tuples
```

## Limitations & Assumptions

- **No wheel slip model:** the equations assume perfect rolling contact. Real Mecanum wheels slip ~10-20% on strafe, so the actual strafe velocity will be lower than commanded. This is fine for teleop; closed-loop control (Slice 6+) would need encoder feedback to compensate.
- **Flat ground only:** the model assumes the chassis is level. On a slope, gravity components would need to be added.
- **`wheel_base` estimate:** measured as front-to-back wheel centre distance. For a square chassis this equals `track_width`. If the real value is off, pure rotation will still work (it only depends on $K$ scaling), but the relative weighting of strafe vs. turn will be slightly wrong.

## Next Steps

- [[Progress]] — build & test log for Slice 5
- [[Slice-6-Overview]] — vision & gimbal (the right stick will be double-tasked here)
