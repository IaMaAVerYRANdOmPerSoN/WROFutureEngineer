# Subsystem Interactions

When engineering a complex robot, it is not enough to design each subsystem independently. The mechanical, electrical, sensing, software, and control systems must work together as one system. A change in one subsystem can change the requirements for several others, so we use the interfaces between subsystems to reason about the complete robot.

We make our interfaces explicit throughout our [codebase](https://apostla-api-reference.web.app/_modules/piclient/core/vision/data.html) and documentation. Each subsystem has a clear purpose, and the inputs and outputs are well-defined. This gives us some flexibility to change the internal implementation of a subsystem without affecting the rest of the system, as long as the interface remains consistent. It also allows us to reason about the interactions between subsystems and identify potential issues before they arise.

## System Overview

The robot is a rear-wheel-drive vehicle with front servo steering. An OV5647 camera provides the main environmental input to a Raspberry Pi 5. The Raspberry Pi processes the camera frames, selects the current challenge behavior, and sends drive commands to an Arduino Uno over USB serial. The Arduino generates the PWM signals for the ESC and steering servo.

The main interaction chain is:

1. **Power system** supplies the motor, ESC, servo, Raspberry Pi, camera, and Arduino.
2. **Camera and mounting system** provide images with a field of view that includes the walls and colored pillars.
3. **Vision system** converts each image into wall, corner, and obstacle measurements.
4. **State machine and controller** select the current maneuver and calculate the steering and speed command.
5. **Serial communication system** transfers the latest command to the Arduino without blocking the control loop.
6. **Arduino and drivetrain** turn the command into physical motion, which changes the next camera image.

This forms a feedback loop: the robot moves, the camera observes the new position, and the controller corrects the next movement.

## Subsystem Interface Map

| Subsystem | Provides | Depends on | Main interaction |
| ---------- | -------- | ---------- | ---------------- |
| Chassis and drivetrain | Motion, traction, steering response | Battery power, ESC, servo commands | Converts control output into robot position and velocity |
| Power system | Battery and regulated voltage rails | Battery, regulator, wiring | Supplies stable power while limiting voltage drop and noise |
| Camera and mount | 640x480 image frames up to 62.50 fps | Raspberry Pi power, rigid mounting, lighting | Determines what the vision pipeline can observe |
| Vision process | Wall and obstacle measurements | Camera frames, HSV thresholds, ROI configuration | Sends fresh perception data to the main process |
| State machine | Challenge state and maneuver selection | Vision measurements, lap and turn tracking | Converts detected track conditions into behavior |
| PD controller | Steering correction and speed command | Wall or pillar target, tuned gains | Calculates the response needed to stay on the desired path |
| Serial interface | Asynchronous drive-command transport | USB connection, Arduino protocol | Transfers the newest command to the hardware controller |
| Arduino and actuators | PWM for ESC and servo | Serial commands, battery or USB power | Applies the requested speed and steering angle |
| Recorder and logs | Video, telemetry, and replay data | Shared frames, main-process log records | Provides evidence for tuning and risk reduction |

## Mechanical and Control Interaction

The mechanical design determines how the control system's commands affect the robot. The front servo uses a steering range of 30-150 degrees, with 90 degrees representing straight ahead. The rear-wheel-drive system was selected because it is lighter and simpler than front-wheel or four-wheel drive, but it also makes traction and steering stability important parts of controller tuning.

The controller therefore cannot be tuned independently of the drivetrain:

1. A larger steering correction changes the robot's turning radius and may make the robot oscillate between the walls.
2. A higher drive speed reduces the time available for the camera and controller to correct an error.
3. A camera mounted high on the mast improves the view of the track but also changes the perspective and the relationship between pixel measurements and physical distance.
4. Motor torque and available battery current limit how quickly the robot can accelerate after a turn.

For this reason, speed, PD gains, steering limits, and camera geometry are tuned together. A software improvement is only useful if the drivetrain can produce the requested response reliably.

## Power and Electrical Interaction

The Gens Ace 1300mAh 2S LiPo provides the main 7.4V supply. The drive motor and ESC use the battery rail directly, the ESC BEC powers the steering servo, and a buck regulator supplies 5V to the Raspberry Pi. The camera receives power through the Raspberry Pi, while the Arduino communicates with the Pi over USB.

The power architecture affects every other subsystem:

- Drive motor acceleration and servo movement create current spikes that can reduce the voltage available to the Raspberry Pi.
- A Raspberry Pi brownout can stop the vision and control processes even if the mechanical system is still powered.
- Motor and servo switching can introduce electrical noise into communication or sensor signals.
- The regulator and wiring must support the computational load of vision processing as well as the instantaneous actuator load.

The system is therefore organized so that high-current actuator loads and regulated compute power have clear supply paths. Connectors and cable routing also matter because a loose power connection can appear as a software or communication failure.

## Perception and Behavior Interaction

The camera is the primary sensor for both challenges. Frames are captured by the camera process and written into shared memory. A pipe signals the vision process when a new frame is available, so the image does not need to be copied between processes.

The vision process selects the challenge-specific interpretation:

- In the **open challenge**, black-pixel counts in left, right, and center regions estimate wall position and detect a wall ahead. The difference between the left and right measurements becomes the wall-following error.
- In the **obstacle challenge**, HSV masks and contours detect red and green pillars in addition to the walls. The controller targets the gap between a pillar and the nearby wall. Green pillars are passed on the left and red pillars are passed on the right.

The state machine adds temporal context to these measurements. For example, a corner is confirmed over several consecutive frames before a turn is started. This prevents one noisy frame from changing the robot's maneuver. During an obstacle response, the pillar target receives 85% of the control weight and the wall target receives 15%, allowing the robot to prioritize the gap while retaining general wall awareness.

## Software and Communication Interaction

The software is divided into parallel processes so that image capture, perception, recording, and control can progress independently. The main process waits for fresh vision results, runs the state machine and PD controller, and submits the resulting command to the `DriveCommandExecutor`.

The executor is an important interface between software timing and hardware timing:

1. The control loop can submit a command every frame without waiting for serial I/O.
2. The executor stores only the latest command.
3. A background worker sends the command when the serial link is available.
4. If a newer command arrives first, the older command is discarded.

This latest-wins behavior prevents serial latency from creating a backlog of obsolete steering commands. The Arduino client uses transaction IDs to match responses and respects `WAITMS` responses from the Arduino, which provides back-pressure when the hardware needs time before accepting another command.

## Data Freshness and Failure Behavior

The system is designed around fresh data rather than processing every item in sequence. Old camera frames, old vision results, and old drive commands are allowed to be dropped because they describe a past robot position.

This design gives each interface a clear failure behavior:

- If vision takes too long, the main process should use the newest available result rather than a growing queue of old results.
- If serial transmission is slow, the executor replaces the pending command rather than delaying newer corrections.
- If a pillar is not detected reliably, the obstacle behavior can fall back toward wall following instead of treating a single uncertain detection as a confirmed maneuver.
- If the recorder is enabled, it observes the system for replay and diagnosis but does not need to block the control loop.

The most important limitation is that the camera is the only sensor currently used by the challenge runners. Lighting changes, occlusion, and camera vibration can therefore affect both perception and control. This is an intentional trade-off: the single-camera approach reduces weight, cost, synchronization work, and additional failure modes, while HSV calibration and repeated track testing address its limitations.

## Interaction-Driven Design Decisions

The following decisions were made because of subsystem interactions rather than because one component was optimal in isolation:

1. **Rear-wheel drive** was chosen because the simpler drivetrain reduces mechanical complexity and leaves more room for reliable software and testing.
2. **A tall camera mount** was chosen because the view of the track is more useful to vision than a low mount, even though the geometry must be accounted for during tuning.
3. **A single OV5647 camera** was chosen because it provides the required color information without the data-fusion and synchronization cost of extra sensors.
4. **Parallel processes and shared memory** were chosen because blocking camera capture or image copies would reduce the control loop's responsiveness.
5. **Latest-wins command scheduling** was chosen because a fresh steering correction is more valuable than guaranteed delivery of an outdated command.
6. **A conservative obstacle target blend** was chosen because obstacle avoidance must work with the wall-following behavior rather than completely replacing it.

## Summary

The robot's performance is determined by the interactions between its subsystems. Mechanical geometry limits the response that the controller can request, the power system determines whether compute and actuation remain stable, and the camera placement determines the quality of the measurements used by vision. The software architecture connects these constraints through fresh-data pipelines, challenge-specific state machines, and asynchronous serial commands.

The system is successful when the complete feedback loop remains stable: the camera observes the track, vision provides useful measurements, the controller makes a timely decision, the Arduino applies it, and the drivetrain produces predictable motion for the next observation. This is why changes are tested at the system level rather than judged only by the performance of an individual subsystem.
