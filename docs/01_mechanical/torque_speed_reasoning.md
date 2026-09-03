# Torque and Speed Reasoning

[Back to README](../../README.md)

---

## Hardware Used

- **Motor:** Furitek Micro Komodo 1212 brushless motor, 3450 KV
- **Voltage:** 7.4V (2S LiPo)
- **Wheel diameter:** 35mm
- **Gear ratio:** 1:4 (motor to wheel)
- **Vehicle mass:** 467g

---

## Calculations

**No-load motor RPM at 7.4V:**
```
RPM = KV × Voltage = 3450 × 7.4 = 25,530 RPM
*While max power*
```

**Wheel RPM after gear reduction:**
```
Wheel RPM = 25,530 ÷ 4 = 6,383 RPM
*While max power*
```

**Linear speed at wheel:**
```
Wheel circumference = π × 35mm = 110mm = 0.11m
Speed = 6,383 RPM × 0.11m ÷ 60 = ~11.7 m/s (theoretical no-load max)
```

In practice, the robot runs at 30–40% throttle in software, giving an effective competition speed of approximately **1.5–2.0 m/s**, which is well within the camera's ability to process frames and react.

---

## Design Reasoning

- **Why this motor was selected:** The Micro Komodo 1212 is compact and lightweight at 17.5g while delivering 120W of power. It spins smoothly at all speeds with no cogging, which is critical for consistent wall-following behavior. See [Motor Selection](./mechanical_reasoning.md#motor-selection) for the full comparison.
- **Why this wheel size was selected:** 35mm wheels were chosen after the purchased off-the-shelf differential was found to sit too low. The 35mm diameter raised the chassis enough to give the differential adequate ground clearance without requiring a full redesign of the chassis geometry.
- **Why this speed range is suitable:** The robot needs to react to walls and obstacles within the time it takes to travel one camera frame's worth of distance. At 2.0 m/s and 62.5 fps, the robot travels approximately 3.2 cm per frame, fast enough to complete laps in time but slow enough for the vision pipeline to detect and react to corners and pillars reliably.
- **Why this torque level is suitable:** The 1:4 gear ratio multiplies the motor's torque by 4 at the wheel, providing enough force to accelerate the 467g chassis from a stop and maintain speed through corners. The ratio was selected to balance torque and top speed, a higher ratio would reduce top speed unnecessarily, and a lower ratio would reduce low-speed torque.

---

## Trade-Offs

- **Higher speed advantages:** Faster lap times; more time to react during the run if something goes wrong.
- **Higher speed disadvantages:** Less time per camera frame to detect corners and pillars; more aggressive PD corrections needed; increased risk of crashing into walls during sharp turns.
- **Higher torque advantages:** Better acceleration from stops; more reliable movement on imperfect surfaces; less likely to stall mid-turn.
- **Higher torque disadvantages:** Requires a higher gear ratio which reduces top speed; increased stress on the 3D printed differential gears.

---

## Testing Evidence

| Test | Configuration | Observation | Conclusion |
|------|---------------|-------------|------------|
| Motor torque under load | New differential gearbox, 7.4V | Motor spinning but robot unable to move after sharp turns | Possible gearbox friction or gear slipping under load |
| Speed at 30% throttle | 35mm wheels, 1:4 ratio, 7.4V | Robot moves at controllable speed suitable for wall following | 30–40% throttle is the appropriate operating range |
| 3D printed differential durability | 3D printed differential, various speeds | Differential broke too often under normal use | Switched to pre-built differential gearbox |
| ESC calibration | Furitek Lizard Pro | Uncalibrated ESC caused loss of torque at expected throttle values | ESC must be calibrated to match code's PWM pulse range |

---

## Final Decision

The Furitek Micro Komodo 1212 at 7.4V with a 1:4 gear ratio and 35mm wheels gives a theoretical top speed of ~11.7 m/s, but the robot is intentionally limited to 30–40% throttle in software for a competition speed of approximately 1.5–2.0 m/s. This range keeps the robot within the reaction capability of the 62.5 fps vision pipeline while providing enough torque through the gear reduction to move the 467g chassis reliably through corners. The 35mm wheel size was also a practical fix for ground clearance issues introduced by the off-the-shelf differential.