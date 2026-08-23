### Mechanical Reasoning
---

### Motor Selection

<table>
<tr>
<td width="50%" valign="top" style="border: 1px solid #888; border-radius: 6px; padding: 12px;">

#### Generic DC motor
A DC motor is simple, cheap, and easy to control with a basic circuit. It works well for basic speed control but spins unevenly at low speeds, which makes precise movement difficult.
 
</td>
<td width="8%"></td>
<td width="50%" valign="top" style="border: 1px solid #888; border-radius: 6px; padding: 12px;">

#### Furitek Micro Komodo 1212 
A small but powerful brushless motor rated at 3450 KV and 120W. It needs a brushless ESC to run but spins smoothly at any speed with no jitter.
 
</td>
</tr>
</table>

---
 
#### Motor Choice
The Micro Komodo spins smoothly at all speeds, which is important for our wall-following code to keep the robot at a steady distance from the walls. A regular DC motor would cause the robot to move unevenly at low speeds, leading to unpredicable movement.
 
---



#### Size Reasoning
Our robot is 24cmx10cmx28cm because the robot has a high vertical length, the camera is able to capture imagery from a steeper view, enabling for a more accurate perspective transformation.

---

#### Drive System
Using a rear wheel drive (RWD):
- Provides a stronger grip on surfaces since the rear of the robot is heavier 
- Since the front wheels are only used for steering, the car can turn more precisely

---


#### Servo Motor
We selected a standard servo motor for steering because they provide precise control, equating to reliable turns.

---