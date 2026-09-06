# Mechanical Reasoning

[Back to README](../../README.md)

---

## Size Reasoning

Our robot measures 24 x 10 x 28 cm. The camera is mounted on a tall vertical mast, which provides a significant advantage over the terrain and enhances vertical resolution after perspective transforms are applied.

## Motor Selection

<table>
<tr>
<td width="50%" valign="top" style="border: 1px solid #888; border-radius: 6px; padding: 12px;">

### Generic DC motor

A DC motor is simple, cheap, and easy to control with a basic circuit. It works well for basic speed control but spins unevenly at low speeds, which makes precise movement difficult.

</td>
</tr>
<tr>
<td colspan="2" valign="top" style="border: 1px solid #888; border-radius: 6px; padding: 12px;">


### Furitek Micro Komodo 1212

A small but powerful brushless motor rated at 3450 KV and 120W. It needs a brushless ESC to run but spins smoothly at any speed with no jitter.

</td>
</tr>
</table>


## Motor Choice

The Micro Komodo spins smoothly at all speeds, which is important for our wall-following code to keep the robot at a steady distance from the walls. A regular DC motor would cause the robot to move unevenly at low speeds, leading to unpredictable movement.

<table>
<tr>
<td width="65%" valign="top">

### Potential Improvements
- Experiment with 10 : 58 – 14 : 58 combinations to tune the balance between torque and top speed.
- Upgrade or lubricate bearings to reduce friction and improve consistency over multiple heats.

</td>
<td width="35%" valign="top">

### Performance Specifications
- KV: **3450 rpm/V**  
- No-load @10V: **0.7 A**  
- Power: **120 W**  
- Battery: **2–3S LiPo**  
- Resistance: **0.16 Ω**  
- Max Current: **10 A**  
- Slot/Pole: **12**  
- Shaft: **1.5 × 6 mm**  

</td>
</tr>
</table>


---

## Drive System

**Gear ratio:** 1:4 (motor to wheel)
The WRO Future Engineer rules do not allow differential drive or omnidirectional wheels, Thus narrowing the solution space to effectively 3 options: Rear-Wheel Drive (RWD), Front-Wheel Drive (FWD), and 4-Wheel Drive (4WD). Each of these options has its own advantages and disadvantages, which are summarized in the table below.

| | **RWD** | **FWD** |
| - | --- | --- |
| **Advantages** | Simplest design, fewer parts, lighter weight, better acceleration | Better traction on slippery surfaces |
| **Disadvantages** | Less stable at high speeds, more difficult to control | Prone to skidding, Complex steering mechanism |

We chose RWD because it is the simplest design, which makes it easier to build and maintain. It is also lighter than FWD, which improves acceleration and reduces power consumption. The robot will not be moving at high speeds, so stability is not a major concern. With FWD, the steering mechanism is extremely complex, especially considering that the vast majority of components are designed in-house and 3D printed. The complexity of FWD would make it difficult to design, test, and maintain the robot in a competition environment. We couldn't make a reliable and robust 3D printed differential gear, let alone a complete FWD system. RWD is the best option for our robot because it is the simplest option that satisfies our design constraints (We do not operate at speeds where RWD becomes problematic.) It is also the most reliable option, which is important in a competition environment.

## Steering System

- **Steering type:** Parallel (Zero-Ackermann)
- **Actuator used:** Hitec HS-5055MG servo motor
- **Steering linkage:** Servo-actuated rack and pinion, moving both front wheels through a shared tie rod so they turn to the same angle rather than the different angles a true Ackermann linkage would use
- **Steering range:** 30-150 degrees (90 is straight), limited by rack travel and chassis clearance, not by the servo's own 0-180 degree range
- **Why selected:**
    - A servo gives direct, repeatable position control, the steering angle the PD controller calculates each frame can be commanded and held without extra feedback hardware, unlike a plain DC motor.
    - Rack and pinion is simple to 3D print and assemble reliably compared to a multi-link Ackermann setup, and converts the servo's rotational output into linear rack travel directly.
    - True Ackermann geometry only pays off at speeds where the inner/outer wheel angle difference meaningfully reduces tire scrub. At the robot's operating speed of 1.5-2.0 m/s (see [torque_speed_reasoning.md](./torque_speed_reasoning.md)), that difference doesn't matter enough to justify the added linkage complexity.

---

## Servo Motor

We selected a standard servo motor for steering because it provides precise and repeatable control of the front wheels. Unlike a motor that would need additional position feedback and a more complicated control system, a servo can move directly to a commanded angle and hold that position. This makes it easier for the robot to follow the steering angles calculated by our control code and helps it make consistent turns.

A servo motor also fits well with our focus on simplicity and reliability. Its compact size and straightforward interface make it easy to mount and connect to the robot's control system, while its position control reduces the risk of over or under-steering. Reliable steering is especially important in a competition environment, where small errors in each turn can accumulate and cause the robot to leave the intended path.


### HS-5055MG 11.9g Metal Gear Digital Micro Servo

- **Operating Voltage:** 4.8V – 6.0V DC
- **Max Torque:** 22 oz/in (1.6 kg/cm)
- **Speed:** 0.17s/60° @ 6.0V
- **Stall Current:** 700 mA
- **Gear Material:** Metal
- **Weight:** 9.5 g
- **Circuit Type:** G1 Programmable Digital

**Where to Buy:** [Click Here](https://hitecrcd.com/hs-5055mg-economy-metal-gear-feather-servo/?srsltid=AfmBOooq_9U4Nehv90Y-tGWqZeo6_1c0_7imuMD9W_dBJmYS1m0sd2Y_)

### Potential Improvements
- Improve response time. This servo motor is not as quick as higher-end micro servos, which reduces steering precision during sharp turns.
- Upgrade to a higher-torque digital micro servo for more reliable steering.

This servo motor was chosen for its compact size, strong torque, and durable metal gears, making it great for precise steering control.

