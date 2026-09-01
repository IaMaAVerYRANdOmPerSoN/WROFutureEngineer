# WRO Future Engineers 2026

## Major Problems

### 1. Differential Gear

- Online differential design failed under load ([Week 11](#week-11-mar-11-18))
- First custom design broke during testing ([Week 11](#week-11-mar-11-18))
- Middle axle broke during assembly ([Week 16](#week-16-apr-20-27))
- Melted from running the robot too fast ([Week 17](#week-17-apr-28-may-5))
- Continued dragging on the ground after reprinting ([Week 16](#week-16-apr-20-27))
- Still not working after multiple iterations ([Week 18](#week-18-may-6-13))
- Fixed then broke again ([Week 20](#week-20-may-22-29), [Week 23](#week-23-june-14-21))
- Gear connecting to motor wears out after 1-2 days ([Week 25](#week-25-june-28july-5))
- Purchased off-the-shelf differential was too large and hit the ground; new wheels bought to raise ride height ([Week 28](#week-28-aug-2-5), [Week 29](#week-29-aug-5-10))
- Axle connectors too loose for the differential output ([Week 30](#week-30-aug-10-15))
- Axle slipping in the differential gearbox (incorrectly identified as lack of torque) ([Week 32](#week-32-aug-18-21))

### 2. Camera

- Error persisted for three weeks ([Week 12](#week-12-mar-19-26), [Week 13](#week-13-mar-27-apr-3))
- Confirmed hardware fault — I2C error on OV5647 sensor; resolved by borrowing a replacement ([Week 15](#week-15-apr-12-19))

### 3. Raspberry Pi

- First Pi broke for unknown reasons ([Week 18](#week-18-may-6-13))
- Second Pi broke — LED error code 4 long 3 short (RP1 not found), unknown cause ([Week 32](#week-32-aug-18-21))

### 4. Power System

- Deans-T connector melted ([Week 14](#week-14-apr-4-11))
- Voltage regulator short circuited; port broke ([Week 19](#week-19-may-14-21))
- Wiring broke and required re-soldering ([Week 31](#week-31-aug-15-17))

### 5. Open Challenge Code

- Unnecessary Hybrid state and oscillation bug between Turn and Follow Wall states ([Week 17](#week-17-apr-28-may-5))
- PD values poorly tuned; robot crashed into inner walls ([Week 24](#week-24-june-22-29))
- Lap counting issues ([Week 24](#week-24-june-22-29))

### 6. Obstacle Challenge

- Robot driving sideways despite correct steering indicator ([Week 27/28](#week-2728-jul-31aug-1))
- Wall distances appearing swapped in vision output ([Week 27/28](#week-2728-jul-31aug-1))
- Color encoding bug causing wrong pillar colors in replay ([Week 28](#week-28-aug-2-5))
- Steering gimbal broke multiple times ([Week 28](#week-28-aug-2-5), [Week 31](#week-31-aug-15-17))

---

# Journal

## Week 1 (Dec 22–29)

- GitHub repository created.
- Async RPC implemented between PiClient and ArduinoServer.
- Async PiCamera2 wrapper created; obstacle detection and field boundary checking developed.

## Week 2 (Dec 30–Jan 6)

- Main file and template test file created; API documentation started.
- Multiprocessing implemented across three processes; obstacle avoidance logic built; AsyncVisionProcessor calls simplified.
- Tests directory created; camera unit tests run.

## Week 3 (Jan 7–14)

- Motor and servo libraries added; AsyncCamera resolution increased; CommProtocol max speed adjusted.
- AsyncCamera and VisionProcessor refactored; multiprocessing added for camera and vision.
- Shopping list added.

## Week 4 (Jan 15–22)

- WRO Future Engineers 2026 rules released.
- Component search began.
- Fusion 360 prototype created.

## Week 5 (Jan 23–30)

- First KiCad schematic draft completed.
- Footprints, symbols, and labels added to KiCad library.
- PCB routing started.
- Steering PWM fixed; vision.py entry point added.

## Week 6 (Jan 31–Feb 6)

- First 3D print of chassis completed.

## Week 7 (Feb 7–14)

- STEP file added for initial prototype.
- Logging, shared memory, and plan.md refactored.
- Engineering journal README created.

## Week 8 (Feb 15–22)

- Wheels purchased.

## Week 9 (Feb 23–Mar 2)

- Physical robot assembly began.

## Week 10 (Mar 3–10)

- Servo and drive motor functioning together.
- New differential gear assembly created.
- Documentation outline created.

## Week 11 (Mar 11–18)

- Online differential design failed under load.
- First custom differential failed structurally during testing.
- Second reinforced differential designed and printed.

## Week 12 (Mar 19–26)

- Camera error encountered.

## Week 13 (Mar 27–Apr 3)

- Camera error persisting.
- Multiprocessing bugs fixed; memory leak checks added.
- Project structure refactored; async vision processing implemented.
- Async vs multiprocessing architecture decision made: overlapping only helps when capture + processing time exceeds the frame interval.

## Week 14 (Apr 4–11)

- Camera intermittent; root cause unknown.
- Deans-T connector melted; replaced.
- First draft of open challenge code completed.
- Obstacle challenge code started.
- Coach Zoom meeting — [see comments](../coach_comments.md#april-8th).
- Arduino code reviewed; issues identified.
- General bugfix pass done.

## Week 15 (Apr 12–19)

- Coach flagged differential ground clearance issue.
- Coach reviewed open challenge code — [see full review](../coach_comments.md#april-15th).
- LiDAR placement under discussion.
- Camera confirmed as hardware fault — I2C error on OV5647; replacement camera borrowed.
- Off-the-shelf differential explored as backup.
- 20A power switch sourced and installed.
- Motors confirmed spinning at 30% throttle.

## Week 16 (Apr 20–27)

- LiDAR mount printed and installed; chassis raised to accommodate.
- Robot confirmed able to scan walls and obstacles.
- Differential middle axle broke; reprinted but still dragging on ground.
- Switched to smaller power switch.
- Voltage regulator mount created.
- Code refactored; utilities package added; coach review requested.
- Vision pipeline partially working; color thresholds need tuning.
- Camera and servo half working.

## Week 17 (Apr 28–May 5)

- Coach removed Hybrid state from open challenge; simplified to two states.
- Fixed oscillation bug between Turn and Follow Wall states using hysteresis.
- Updated and pushed open_challenge.py.

## Week 18 (May 6–13)

- Differential melted from running too fast; reprinted and upgraded.
- Reflashed SD card but still could not connect; Raspberry Pi confirmed broken.

## Week 19 (May 14–21)

- Differential still not working; decided to buy one if not fixed by next week.
- Voltage regulator short circuited; port broke.

## Week 20 (May 22–29)

- Differential fixed and working.
- Voltage regulator repair in progress.

## Week 21 (May 30–June 5)

- Fixing open challenge issues.

## Week 22 (June 6–13)

- Open challenge still in progress.
- Most time spent on exams.

## Week 23 (June 14–21)

- Primary coder left for China; difficulty navigating code through RealVNC.
- Differential broke again.

## Week 24 (June 22–29)

- PD values poorly tuned; robot crashing into inner walls.
- Lap counting still an issue.
- Open challenge completed.
- Wire to motor disconnected; re-soldered.

## Week 25 (June 28–July 5)

- Motor gear wearing out after 1-2 days; taped as temporary fix.
- Corner turn PD biasing proposed.
- PCB shipped to Toronto.
- Coach flagged lack of code structure documentation; auto-generated docs created and hosted online.
- Config system updated to support TOML file overrides.
- Coach requested software diagram in main README.

## Week 26 (July 6–12)

- Vision and open challenge code updated with new tuning values; confirmed working.
- Obstacle challenge testing started; obstacles excluded during preliminary testing.

## Week 27 (July 22–26)

- Obstacle challenge code completed and ready to test.
- Test video recorded by pushing robot by hand; replay system working without needing the physical robot.
- Bug found in obstacle challenge; fix not yet identified.
- Coach noted walls need to be flipped to avoid glare affecting detection.
- VS Code extension host crashing due to Pylance using 1.7GB RAM; no easy fix.

## Week 27/28 (Jul 31–Aug 1)

- Bug identified: robot drives sideways despite correct steering indicator; likely a feedback loop from incorrect state entry.
- Coach found wall distances appear swapped and angle direction may be inverted in the vision output.
- Steering gimbal snapped again.
- Camera confirmed at maximum 62.50 fps at 640x480.
- Raspberry Pi Camera Module 3 Wide researched as upgrade (supports 120 fps).
- Extra battery requested from coach.

## Week 28 (Aug 2–5)

- Red pillar color encoding bug found (BGR/RGB mix-up); pillar detection showing progress.
- Differential dragging on the floor again.
- Decided to buy an off-the-shelf differential instead of continuing with the custom printed design.
- Team member away until Monday.

## Week 29 (Aug 5–10)

- Purchased differential arrived but was too large and hit the ground during testing.
- Bought new 35mm wheels to raise the robot's ride height and give the differential enough clearance.
- Robot moving but still a little clanky.
- Checked WRO rules on robot size changes; no rule against it, but robot cannot touch the parking lot walls.
- Explored using last year's parking strategy on a different wall instead of parallel parking.
- Started designing length-extending attachments.

## Week 30 (Aug 10–15)

- Length-extending attachments cancelled.
- Coach found axle connectors too loose for differential output; lifting gearbox would cause new issues.
- Coach provided a smaller differential gearbox from an old RC kit that may fit the existing axles.
- Plan to design two 3D printed parts: gearbox mount and motor-to-shaft connector.
- Measurements and photos of gearbox taken and shared with hardware team member.
- Gearbox confirmed 22mm tall; design work started.

## Week 31 (Aug 15–17)

- New gearbox mount designed and printed.
- Parallel parking FSM completed.
- Fusion 360 source file requested to edit mount design; updated STEP file sent for printing.
- Checked WRO rules on parking lot stick height; no official ruling found. Coach advised proper parallel parking is required.
- Wiring broke; re-soldered.

## Week 32 (Aug 18–21)

- Raspberry Pi showing error code 4 long 3 short (RP1 not found); confirmed dead. Burning smell noticed days prior.
- Backup Pi picked up from coach's mailbox and set up. Fan configured to always run to prevent overheating.
- Differential no longer dragging but motor does not have enough torque; spins but cannot move the robot after sharp turns.
- Likely cause is too much gearbox friction or gears slipping under load.
- Coach suggested updating ESC speed values for the new gear ratio and calibrating the ESC using the FuriCar app.
- Speed constants already updated; camera frame rate limit of 62.5 fps is now the speed ceiling.
- Root cause of torque issue still unknown; coach suggested trying the previous motor.
