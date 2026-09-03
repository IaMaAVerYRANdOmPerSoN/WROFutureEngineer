# 3D Printed Parts

[Back to README](../../README.md)

---

## Turning System

Servo-actuated rack and pinion steering with a curved front bumper for wall sliding in the obstacle challenge.

### Iterations

**Version 1 — Reused from Previous Season**
Carried over from last year's robot. Turning was uniform and robust but the steering horn broke periodically under load.

**Version 2 — Improved Attachability and Steering Horn**
- Redesigned mounting interface to match the robot's base shape, preventing sliding during sharp turns.
- Added a fillet to the steering horn to reduce stress concentration and improve durability.

**Version 3 — Curved Bumper (Final)**
A curved bumper was added to the front of the robot:
- Acts as a shield if the robot contacts a wall.
- Allows the robot to slide off walls cleanly in the obstacle challenge. Without it, the rubber wheels provided too much grip and caused the robot to lodge itself against walls.

<p align="center">
  <img src="../../docs/img/turning_system_final.png" width="600">
</p>
<p align="center"><i>Final version of the turning system showing the curved front bumper.</i></p>

| Version | Change | Problem Solved |
|---------|--------|----------------|
| V1 | Reused from previous season | Steering horn broke periodically |
| V2 | Matched base shape; added fillet to steering horn | Sliding during turns; horn breakage |
| V3 | Added curved front bumper | Robot getting stuck against walls in obstacle challenge |

---

## Raspberry Pi 5 Layout and Camera Mount

Slim rotated design with a separated camera tower angled at 35 degrees downward.

### Iterations

**Version 1 — Adapted from Previous Season**
- Layout rotated and made slimmer to reduce footprint and filament.
- Camera positioned high and angled downward.
- Pillars added to replace alignment screws for easier assembly.

**Version 2 — Separated Tower and Improved Camera Angle (Final)**
- Camera angle increased to 35 degrees. Version 1 was not steep enough — background objects outside the game mat were appearing in the frame.
- Camera tower separated from the RP5 layout. Previously any small change to camera angle required reprinting the entire assembly. Separating the two pieces means only the affected part needs to be reprinted.

<p align="center">
  <img src="../../docs/img/rp5_camera_mount.png" width="600">
</p>
<p align="center"><i>Final version of the Raspberry Pi 5 layout with separated camera tower.</i></p>

| Version | Change | Reason |
|---------|--------|--------|
| V1 | Slimmer rotated design; camera high and angled; pillars for alignment | Reduce size and filament; improve camera position |
| V2 | Camera angle increased to 35°; camera tower separated | Remove background objects from frame; reduce reprint time |

---

## Arduino Uno Layout

Main chassis plate holding the Arduino, servo, and front assembly; redesigned for compactness across three versions.

### Iterations

**Version 1 — Adapted from Previous Season**
- Hole locations updated to match Arduino Uno mounting holes.
- Rectangular cutout added in the middle to reduce filament and print time.

**Version 2 — Thicker Base and Added Support**
The frame was shifting and flexing under load:
- Base plate thickness increased to prevent flexing.
- Additional support added around the rectangular cutout to restore rigidity.

**Version 3 — Servo Repositioned for Compactness (Final)**
- Servo moved rearward, shortening the overall robot length.
- Front section extended and reinforced to support bumper attachment.
- Result: more compact robot with servo better positioned relative to the steering linkage.

| Version | Change | Reason |
|---------|--------|--------|
| V1 | Updated hole positions; rectangular cutout | Match Arduino Uno mounting; reduce filament |
| V2 | Thicker base; support around cutout | Frame shifting and flexing under load |
| V3 | Servo moved rearward; front extended for bumper | Reduce robot length; integrate bumper cleanly |

---

## Connectors

3D printed C-shaped connectors replacing brass standoffs to speed up assembly and disassembly.

### Why Connectors Instead of Standoffs

Assembling last year's robot took too long due to the number of brass standoffs required. Printed connectors allow the two main chassis layers to be separated and reassembled quickly without tools — useful during competition when time is limited.

### Iterations

**Version 1 — Medium Length**
Medium connector length left adequate space between the Arduino Uno and Raspberry Pi layers while the final robot layout was still being determined.

**Version 2 — Extended Length for Front LiDAR**
Connectors lengthened to accommodate a planned front LiDAR sensor. This idea was later abandoned — the camera proved reliable and straightforward enough to handle all detection tasks on its own.

**Version 3 — Shortened to C-Shape (Final)**
Connectors shortened to make the robot as compact as possible. This caused the battery to no longer fit underneath the Arduino Uno layer. The connectors were redesigned into a C-shape to route around the battery, allowing it to stay in its original position while keeping the chassis layers close together.

| Version | Change | Reason |
|---------|--------|--------|
| V1 | Medium length | Space for layout flexibility during early design |
| V2 | Increased length | Planned front LiDAR — later abandoned |
| V3 | Shortened; C-shape profile | Compact final design; C-shape fixes battery clearance |