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

<p align="center">
  <img src="../../docs/img/arduino_layout.png" width="600">
</p>
<p align="center"><i>Final version of the Arduino Uno layout with servo repositioned and bumper support added.</i></p>

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

<p align="center">
  <img src="../../docs/img/connectors.png" width="600">
</p>
<p align="center"><i>Final version of the connectors layout</i></p>

---

## Differential Gear Design

Our differential gear design went through several iterations, each with its own set of trade-offs and limitations. The table below summarizes the different versions of our differential gear design, along with their design goals, limitations, and takeaways.

| Version | Design Goals | Limitations | Takeaways |
| --- | --- | --- | --- |
| 1 | Adapt a preliminary GrabCAD differential with minor modifications. | The design ignored our size constraints. The teeth did not mesh, wore quickly, and broke at increased speed. | Existing designs must be evaluated against our constraints before testing. |
| 2 | Design the differential from scratch around our size constraints. | Gear wear still caused skipping, rapid direction changes caused locking, and poor meshing generated temperatures exceeding PLA glass transition temperatures. | Material constraints and operating conditions must be considered alongside geometry. |
| 3 | Improve meshing and alignment by adding axles inside the rotating cage and securing all moving components. | The added complexity made tolerance tuning difficult. Friction increased wear, and the design couldn't overcome the surface finish limitations of FDM 3D printing. | A more robust design can introduce new friction, tolerance, and manufacturing problems. |
| 4 | Use a robust metal differential designed for RC cars. | The differential was too large for the universal axles, rubbed against the floor, and bent the rear assembly because of its weight. | Components cannot be viewed in isolation; they are constrained by and must be viewed in the context of the entire system. |
| 5 | Use a compact differential gearbox salvaged from a smaller RC car (1/24–1/28). | The gearbox was salvaged rather than purpose-built. No backups available, and the design is not easily reproducible. | The smaller, lighter, self-contained gearbox eliminated 3D-printed gears, reduced complexity, fit the design constraints, and allowed the robot to run smoothly |

Despite pivoting our design in fundamentally different directions two times, we were able to converge on a final design that met our requirements and constraints. Iteration 1-3 focused on mitigating a fundamental material constraint in FDM PLA, while iteration 4-5 were architectural shifts to completely different models that better meet our requirements. We learned that testing more approaches and iterating quickly near the start of the design process is more effective than premature optimization of a single approach.

<p align="center">
  <img src="../../docs/img/differential.png" width="600">
</p>
<p align="center"><i>Final version of the differential layout</i></p>

---