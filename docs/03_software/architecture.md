# Architecture Details

[Back to Software Overview](../../README.md)

---

## The Three Processes

The robot runs three separate OS processes at the same time so that the camera, vision, and control logic never slow each other down.

### Camera Process
- Captures frames from the Pi camera
- Writes each frame directly into shared memory so no copying is needed
- Sends a signal through a pipe to tell the vision process a new frame is ready

### Vision Process
- Reads the frame from shared memory when it gets the signal
- Runs the vision code to find walls and obstacles
- Sends the results through a pipe to the main process
- Multiple vision threads run at once inside this process to keep up with the camera

### Main Process
- Waits for fresh vision results from the vision process
- Runs the state machine and PD controller
- Submits drive commands to the DriveCommandExecutor
- Also handles the debug video overlay

---

## Data Flow

```
Camera Process ──── shared memory (raw frame) ────▶ Vision Process
                  + pipe (frame-ready signal)              │
                                                     pipe (results)
                                                           ▼
Arduino ◀── serial ── DriveCommandExecutor ◀── Main Process & FSM
                        (latest-wins)               │
                                               PD Controller
                                             + State Machine
```

---

## Latest-Wins Design

The system always acts on the freshest data:

- If a new camera frame arrives before the old one is processed, the old one is dropped
- If a new drive command is submitted before the old one is sent to the Arduino, the old one is overwritten
- The vision pipe holds only the 3 most recent results and yields them newest-first

This means the robot never acts on stale data and never builds up a backlog.

---

## Logging and Telemetry

A separate recorder process runs alongside the main processes. It:
- Receives frames from shared memory
- Saves them to a video file
- Receives log records from the main process and saves them via timed pickle dumps
- A replay generator can combine the video and log records into an annotated replay video for post-run analysis

---

[Apostla 0.0.1 documentation](https://apostla-api-reference.web.app/)