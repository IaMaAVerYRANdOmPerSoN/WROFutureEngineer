
# WRO Future Engineers 2026

---

## Week 1 (Dec 22–29)

- GitHub repository created and initial project structure established.
- Implemented fully functional asynchronous RPC between PiClient and ArduinoServer classes, allowing the Raspberry Pi and Arduino to communicate reliably across processes.
- Created an asynchronous wrapper for PiCamera2; developed initial obstacle detection logic and field boundary checking to identify the edges of the competition field.

---

## Week 2 (Dec 30–Jan 6)

- Created main file and template test file; started work on API documentation to formalize inter-module interfaces.
- Implemented multiprocessing across three concurrent processes; constructed obstacle avoidance logic in the main control loop; flattened AsyncVisionProcessor calls into a single unified method to simplify the call stack.
- Created tests directory and ran first camera unit tests to verify capture pipeline integrity.

---

## Week 3 (Jan 7–14)

- Updated platformio.ini and main.cpp to include new motor and servo libraries; modified AsyncCamera for higher resolution output and adjusted CommProtocol to support increased maximum speed.
- Refactored AsyncCamera and VisionProcessor for improved throughput performance; updated frame dimensions, enhanced logging output, and added a comprehensive image analysis method; implemented multiprocessing specifically for the camera capture and vision processing stages.
- Added shopping list for required project components and materials.

---

## Week 4 (Jan 15–22)

- WRO Future Engineers 2026 official rules released and reviewed by the team.
- Began searching for suitable RC car components matching the competition constraints.
- Created a Fusion 360 prototype model of the first build concept.

---

## Week 5 (Jan 23–30)

- Completed first electronics schematic draft in KiCad.
- Added footprints for RGF0040E components; added LM2678S-12 symbol and footprints to the KiCad library.
- Added no-connect flags and net labels; created a ground terminal for the Raspberry Pi power connections.
- Removed stale lock files and updated workspace configuration to include the EDA directory.
- Began PCB routing.
- Fixed steering PWM pin definition in main.cpp; added a proper main entry point to vision.py.

---

## Week 6 (Jan 31–Feb 6)

- Completed the first 3D print of the robot chassis. Parts were inspected for dimensional accuracy and fit.

---

## Week 7 (Feb 7–14)

- Added STEP file for the initial prototype to support mechanical CAD reference.
- Refactored logging setup in vision.py and updated shared memory handling between processes; enhanced plan.md with detailed task breakdowns and author assignments; cleaned up shoppingList.md; added ltex dictionary for spell checking in the editor.
- Created engineering journal README to establish documentation structure.

---

## Week 8 (Feb 15–22)

- Purchased wheels for the robot platform.

---

## Week 9 (Feb 23–Mar 2)

- Began physical robot build and assembly. Components were test-fitted to the chassis.

---

## Week 10 (Mar 3–10)

- Got the servo and drive motor functioning together for the first time on the physical build.
- Created a new differential gear assembly for the drivetrain.
- Created an initial outline for the full engineering documentation required for competition submission.

---

## Week 11 (Mar 11–18)

- Attempted to adapt an existing online differential gear design for the robot — the design did not perform adequately under the torque load of the drivetrain.
- First fully custom-designed differential appeared mechanically sound during CAD review but failed structurally during physical testing.
- Designed and printed a second variation of the differential with reinforced geometry to withstand competition-level forces.

---

## Week 12 (Mar 19–26)

- Camera error encountered during testing. Initial investigation began.

---

## Week 13 (Mar 27–Apr 3)

- Camera error persisting across sessions. Issue not yet resolved.
- Fixed multiprocessing logic bugs and added additional checks for memory leaks.
- Fixed rebase conflicts in the codebase.
- Refactored project structure and implemented asynchronous vision processing.
- Team discussed async and multiprocessing architecture for the vision pipeline. The key design rule established: overlapping frame capture and processing only improves throughput when capture time + processing time exceeds the frame interval. At 30 fps (33 ms interval) with 15 ms capture and 15 ms processing, sequential operation is sufficient. At 60 fps (16.7 ms interval) with the same timings, overlapping is necessary to prevent effective throughput from dropping to approximately 33 fps.

---

## Week 14 (Apr 4–11)

- Camera operating intermittently; root cause not yet identified.
- Melted the Deans-T male connector during wiring; sourced and installed a replacement.
- Completed first draft of the open challenge code.
- Started writing the obstacle challenge code.
- Joined a Zoom meeting with coach — [see coach comments](../coach_comments.md#april-8th).
- Arduino motor and servo control code reviewed; potential logic issues identified for follow-up.
- Conducted a general bugfix pass across the codebase.

---

## Week 15 (Apr 12–19)

- Coach noted that the differential assembly sits too close to the ground, ground clearance adjustment required before competition.
- Coach reviewed the open challenge code — [see full coach review](../coach_comments.md#april-15th).
- Team discussing optimal placement for the LiDAR unit on the chassis.
- Camera failure definitively confirmed as a hardware fault rather than a software or configuration issue. Full diagnostic output showed an I2C read error on the OV5647 sensor (error code -121) and a completely empty I2C bus at address 0x36. OS re-flash produced no change. Most likely cause is a faulty CSI ribbon cable or damaged camera module. A second camera was borrowed from a teammate to continue development.
- Explored sourcing an off-the-shelf differential assembly from AliExpress as a backup to the printed design, in case the custom printed version continues to fail.
- Sourced and installed a 20 A-rated power switch from school supply for the main battery rail. The switch is physically larger than ideal but was the only available option with sufficient current rating and practical solderability at the required wire gauge.
- Motors confirmed spinning at 30% throttle — first confirmed drive output on the current build revision.

---

## Week 16 (Apr 20–27)

- Modeled and 3D printed the LiDAR mount. Installing the mount required raising the rest of the robot chassis upward to accommodate the new geometry.
- Confirmed the robot is able to scan and detect both walls and obstacles using the LiDAR.
- The middle axle on the differential broke during assembly. The component was reprinted, however the differential continues to drag on the ground, ground clearance remains an open issue.
- Decision made to switch from the large 20A power switch to a smaller switch for easier integration. The smaller form factor simplifies wiring and mounting without meaningful risk at expected current draw.
- Created a dedicated mounting location for the step-down voltage regulator on the chassis.
- Code structure significantly refactored: a new utilities package was added and the main package reorganized. Coach review of all updated packages and modules requested.
- Vision pipeline is partially functional. Color detection ranges for the HSV thresholds are not yet well-tuned, the vision test passes but detected color regions are inaccurate under real lighting. Further threshold calibration required under competition lighting conditions.
- New 3D prints completed successfully.
- Camera and servo confirmed as partially working, sufficient for initial software testing but not yet competition-ready.

---

## Week 16 (Apr 28–May 5)
- Coach pointed out that the "Hybrid" state in the open challenge was not needed — having three states instead of two makes the code harder to follow and debug.
- Coach also found a bug where the robot could get stuck switching back and forth between "Turn" and "Follow Wall" repeatedly if the walls were not detected right after a corner.
- Removed the Hybrid state from the code.
Fixed the state switching issue by adding hysteresis and making the turning logic simpler.
Updated and pushed open_challenge.py with the 
changes.
- Forgot to switch to STA mode to AP mode before class started (oops).

---

## Week 17 (May 6–13)
- Differential melted because we ran the robot too quickly.
- Fixed the differential and made it upgraded it to run on quicker speeds.
- Reflashed SD card due to connection issues. However, we stil couldn't connect to our robot.
- Concluded that RaspberryPi broke due to unknown reasons.

---

## Week 18 (May 14-21)
- Tried another differential, it still doesn't work...
- Decided that if we cannot create our own differential by next week, we will buy one off amazon
- Regulator short circuted due to damaged wires caused by getting caught in the motor system
    - Port for the step down regulator broke


## Week 19 (May 22-29)
- Fixed differential... IT WORKS!
- Fixing the step down voltage regulator that short circuited