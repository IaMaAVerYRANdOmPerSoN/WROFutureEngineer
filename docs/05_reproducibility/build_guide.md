# Build Guide

Start by viewing our [GitHub releases page](https://github.com/IaMaAVerYRANdOmPerSoN/WROFutureEngineer/releases/tag/v0.1.0) for the 3D printing files (.f3z, .step, .fxb)

Once printed, make sure you have all the materials in [Material List](./bill_of_materials.md)

We've provided a brief assembly video to help you get started. The video is a high-level overview of the assembly process and does not cover every detail. Please refer to the written instructions below for more detailed guidance.

[![Assembly Video](https://img.youtube.com/vi/6nG1ul_CTjg/0.jpg)](https://youtu.be/6nG1ul_CTjg)

## Turning System

The turning system is responsible for controlling the steering of the robot and allowing the front wheels to rotate smoothly.

### Assembly Steps

1. **Install the Steering Knuckles**
   - Place both steering knuckles inside their respective control arms.
   - Ensure that the knuckles are seated correctly and aligned with the mounting points on the control arms.
   - Check that both steering knuckles can move freely without excessive resistance.

2. **Install the Servo Horn**
   - Attach the servo horn securely onto the steering servo.
   - Ensure that the servo horn is positioned correctly so that it can provide the required range of motion for the steering system.

3. **Attach the Anti-Sway Arm**
   - Connect the anti-sway arm to the servo horn.
   - Make sure the connection is secure and that the arm is able to move through its full range without contacting surrounding components.

4. **Connect the Steering Components**
   - Attach the anti-sway arm to both steering knuckles.
   - Verify that both steering knuckles move together when the servo horn is rotated.
   - Check that there is no excessive play or looseness in the steering linkage.

5. **Install the Bearings and Wheels**
   - Insert the ball bearings into their designated mounting points.
   - Carefully install the wheels onto the steering knuckles.
   - Confirm that the wheels rotate smoothly and that the bearings are seated correctly.

6. **Mount the Turning System**
   - Position the completed turning system onto the Arduino Uno layout.
   - Align all mounting holes before inserting the screws.
   - Secure the assembly firmly while ensuring that the steering mechanism remains free to move.

<p align="center">
  <img src="/docs/img/servo_assembly.png" width="600">
</p>

---

## Differential System

The differential system transfers power from the motor to the wheels while allowing the wheels to rotate effectively during turns.

### Assembly Steps

1. **Mount the Furitek Motor**
   - Position the Furitek motor onto the rotating cage.
   - Align the motor with the designated mounting holes and secure it using the appropriate screws.
   - Ensure that the motor is firmly attached and does not shift during operation.

2. **Install the Rotating Cage**
   - Place the rotating cage into the designated differential layout.
   - Carefully align the cage with the mounting points and ensure that all components are properly seated.
   - Secure the rotating cage using the appropriate screws.

3. **Install the Differential**
   - Position the pre-assembled differential into the rotating cage.
   - Secure the differential firmly in place.
   - Rotate the differential by hand to verify that it moves smoothly without binding or unusual resistance.

4. **Install the Ball Bearings**
   - Insert the ball bearings into their designated positions within the differential assembly.
   - Ensure that each bearing is fully seated and aligned correctly.

5. **Install the Dog-Bone Axles**
   - Insert the dog-bone axles into the differential.
   - Check that the axles are properly engaged with the differential and can rotate freely.

6. **Attach the Wheels**
   - Install the wheels onto the dog-bone axles.
   - Secure each wheel firmly while ensuring that it can rotate without obstruction.
   - Rotate the wheels manually to confirm that the differential and axles operate smoothly.

<p align="center">
  <img src="/docs/img/differential_assembly.png" width="600">
</p>

---

# Main Chassis

The main chassis integrates the turning system, differential system, and electronic components into a single structure.

## Arduino Uno Layout

1. **Install the Drive and Steering Systems**
   - Position the completed differential system onto the Arduino Uno chassis layout.
   - Align the mounting holes and secure the differential system using the appropriate screws.
   - Position the turning system onto the front of the chassis and secure it in place.
   - Confirm that both systems are properly aligned before continuing.

2. **Mount the Arduino Uno**
   - Place the Arduino Uno onto its designated mounting position on the chassis.
   - Align the mounting holes and secure the board using the appropriate screws and hardware.
   - Ensure that the board is firmly mounted without placing unnecessary pressure on the PCB.

3. **Install the Chassis Connectors**
   - Attach the four connectors to their designated mounting locations.
   - Align each connector carefully with the chassis.
   - Secure all four connectors using the appropriate screws.
   - Verify that the connectors are firmly attached and do not interfere with any moving components.

4. **Final Mechanical Check**
   - Inspect the entire Arduino Uno layout for loose screws or incorrectly positioned components.
   - Rotate the wheels manually to ensure that the drivetrain operates smoothly.
   - Move the steering system through its full range of motion to confirm that there are no mechanical obstructions.

<p align="center">
  <img src="/docs/img/core_assembly.png" width="600">
</p>

---

## RP5 Layout

The RP5 layout provides the mounting structure for the robot's computing hardware, camera system, and electronic speed controller.

### Assembly Steps

1. **Install the Chassis Connectors**
   - Position the four connectors onto their designated mounting points on the RP5 layout.
   - Align the connectors carefully with the chassis holes.
   - Secure each connector using the appropriate screws.

2. **Mount the RP5**
   - Carefully position the RP5 onto the designated mounting area.
   - Align the board with the four connectors.
   - Secure the RP5 firmly using the appropriate screws.
   - Ensure that the board is stable and that no cables or components are being compressed.

3. **Install the Camera Mast**
   - Position the camera mast onto its designated mounting location.
   - Align the mounting holes and secure the mast using the appropriate screws.
   - Confirm that the mast is straight and firmly attached to the chassis.

4. **Mount the Camera**
   - Attach the camera to the top of the camera mast.
   - Secure the camera so that it remains stable during robot movement.
   - Adjust the camera orientation to provide a clear forward-facing view.

5. **Install the ESC**
   - Slide the ESC into its designated position within the RP5 layout.
   - Ensure that the ESC is securely positioned and that its cables have sufficient clearance.
   - Route the cables neatly to prevent them from interfering with the wheels, drivetrain, or steering components.

6. **Final Assembly Inspection**
   - Check that all hardware is securely fastened.
   - Confirm that the camera mast and camera are stable.
   - Ensure that all electronic components are properly positioned and that no wires are obstructing moving mechanical components.
   - Manually test the wheels and steering one final time before powering on the robot.

<p align="center">
  <img src="/docs/img/core_assembly.png" width="600">
</p>