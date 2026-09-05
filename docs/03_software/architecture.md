# Architecture Details

[Back to Software Overview](../../README.md)

## The Four Processes

The robot runs four separate OS processes in parallel so that the camera, vision, and main control loop are pipelines rather than sequential. This raises effective throughput to the maximum of the four, rather than the sum of the four.

### [`Camera`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.AsyncCamera) Process

- Captures frames from the Pi camera through [`AsyncCamera`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.AsyncCamera)
- Writes each frame directly into shared memory, so no copying is needed
- Sends a signal through a pipe to tell the vision process a new frame is ready

### [`Vision`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.VisionProcessor) Process

- Reads the frame from shared memory when it gets the signal
- Runs [`VisionProcessor`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.VisionProcessor) and the challenge-specific [`OpenChallengeVisionProcessor`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.OpenChallengeVisionProcessor) or [`ObstacleChallengeVisionProcessor`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.ObstacleChallengeVisionProcessor) to find walls and obstacles
- Sends the results through a pipe to the main process
- Multiple vision threads run at once inside this process to keep up with the camera

### [`Recorder`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Recorder) Process

- Reads frames from shared memory and saves them to a video file
- Receives log records from the main process and saves them via timed pickle dumps
- A replay generator can combine the video and log records into an annotated replay video for post-run analysis
- The [`Recorder`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Recorder) process is optional and can be disabled to save CPU cycles if logging is not needed

### Main Process

- Waits for fresh vision results from the vision process
- Runs the [`StateMachine`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.StateMachine) and [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) controller
- Submits drive commands to [`DriveCommandExecutor`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.DriveCommandExecutor)
- Also handles the debug video overlay

## Data Flow

<p align="center">
  <img src="/docs/diagrams/architecture.webp" width="750" alt="Architecture diagram showing the four processes and their data flow" />
</p>
<p align="center"><i>Data flow diagram for the four processes.</i></p>

## Latest-Wins Design

The system always acts on the freshest data:

- If a new camera frame arrives before the old one is processed, the old one is dropped
- If a new drive command is submitted before the old one is sent to the Arduino, the old one is overwritten
- The vision pipe holds only the 3 most recent results and yields them newest-first

This means the robot never acts on stale data and never builds up a backlog.

## API and implementation map

The [Apostla API Reference](https://apostla-api-reference.web.app/) documents the public package. Use the source links below when the design discussion needs implementation detail.

| Area | Public API | Implementation |
| ---- | ---------- | -------------- |
| Camera | [`AsyncCamera`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.AsyncCamera), [`get_frame_async()`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.AsyncCamera.get_frame_async), [`stream()`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.AsyncCamera.stream) | [`async_camera.py`](https://apostla-api-reference.web.app/_modules/piclient/core/interface/async_camera.html) |
| Serial drive | [`Client`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Client), [`drive_motors()`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Client.drive_motors), [`set_servo_angle()`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Client.set_servo_angle), [`set_motor_speed()`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Client.set_motor_speed) | [`client.py`](https://apostla-api-reference.web.app/_modules/piclient/core/interface/drive/client.html) |
| Command scheduling | [`DriveCommandExecutor`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.DriveCommandExecutor), [`submit()`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.DriveCommandExecutor.submit) | [`comm_protocol.py`](https://apostla-api-reference.web.app/_modules/piclient/core/interface/comm_protocol.html) |
| Vision | [`VisionProcessor`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.VisionProcessor), [`VisionObject`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.VisionObject), [`OpenChallengeWalls`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.OpenChallengeWalls), [`WallsAndObstacles`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.WallsAndObstacles) | [`base.py`](https://apostla-api-reference.web.app/_modules/piclient/core/vision/base.html), [`data.py`](https://apostla-api-reference.web.app/_modules/piclient/core/vision/data.html), [`open_challenge.py`](https://apostla-api-reference.web.app/_modules/piclient/core/vision/open_challenge.html) |
| Control | [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD), [`PD.tick()`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD.tick), [`StateMachine`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.StateMachine), [`TransitionManager`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.TransitionManager) | [`controller.py`](https://apostla-api-reference.web.app/_modules/piclient/core/lib/controller.html) |
| Configuration | [`Config`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config), [`GLOBAL_CONFIG()`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.GLOBAL_CONFIG), [`Freezeable.freeze()`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Freezeable.freeze) | [`config.py`](https://apostla-api-reference.web.app/_modules/piclient/core/lib/config.html) |
| Challenge entry points | [`run_open_challenge()`](https://apostla-api-reference.web.app/open_challenge.html#piclient.open_challenge.run_open_challenge), [`run_obstacle_challenge()`](https://apostla-api-reference.web.app/obstacle_challenge.html#piclient.obstacle_challenge.run_obstacle_challenge) | [`runner.py`](https://apostla-api-reference.web.app/_modules/piclient/open_challenge/runner.html), [`runner.py`](https://apostla-api-reference.web.app/_modules/piclient/obstacle_challenge/runner.html) |
