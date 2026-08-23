# Challenge Runner Details

[Back to Software Overview](../../README.md)

---

## Overview

When you run `wro`, it loads the [`Config`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config), connects to the Arduino through [`Client`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.Client), starts the camera, vision, and recorder processes, and enters the main control loop. The loop runs once per fresh vision result.

Each loop iteration:

1. Gets the latest wall, obstacle, and parking lot data from the vision process
2. Runs it through the [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) controller to calculate a steering correction
3. Checks the [`StateMachine`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.StateMachine) to decide what to do
4. Submits a drive command to the [`DriveCommandExecutor`](https://apostla-api-reference.web.app/interface.html#piclient.core.interface.DriveCommandExecutor)

---

## Open Challenge

### State Machine

| State | What triggers it | What the robot does |
| ----- | ---------------- | ------------------- |
| Straight | Default | Wall follow using [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) controller |
| Turn | Black fill in center ROI confirmed over several frames | Switch to more aggressive PD gains |
| Final Turn | Last turn of the last lap | Same as Turn |
| Final Straight | After the final turn | Drive to stop position |

### Corner Detection

Corners are not triggered on a single frame. The center ROI must fill up with black pixels for [several consecutive frames](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.SharedChallengeConfig) before a turn is triggered. This filters out noise and false detections from shadows or lighting changes.

### Lap Counting

The robot counts completed turns to track laps. The number of turns per lap is set in `piclient.toml` under `[OpenChallengeConfig]` as `LAP_LENGTH_IN_TURNS`. After the required number of turns, the robot begins the shutdown sequence.

### [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) Controller

The steering correction is calculated as:

```python
error = right_wall_distance - left_wall_distance
correction = Kp * error + Kd * (error - previous_error)
servo_angle = correction * 90 + 90
```

Gains `Kp` and `Kd` are set separately for wall following and corner turning in `piclient.toml`.

---

## Obstacle Challenge

### [`StateMachine`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.StateMachine)

Same as the open challenge with one extra state:

| State | What triggers it | What the robot does |
| ----- | ---------------- | ------------------- |
| Straight | Default | Wall follow using [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) controller |
| Turn | Corner detected | Hard steer toward missing wall |
| Obstacle Avoid | Vision returns a pillar target | Steers toward the gap between pillar and wall |
| Final Turn | Last turn of last lap | Same as Turn |
| Final Straight | After final turn | Drive to stop |

### Obstacle Avoidance

When the [`ObstacleChallengeVisionProcessor`](https://apostla-api-reference.web.app/vision.html#piclient.core.vision.ObstacleChallengeVisionProcessor) detects a pillar, it returns a target point — a dynamic, proximity-based, offset from the obstacle towards the relevant wall. The control loop steers toward this target using a separate [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) controller with gains set in `piclient.toml` under `[ObstacleChallengeConfig]`.

Obstacle avoidance takes priority over wall following. Once the pillar clears the frame, the robot returns to normal wall following.

**WRO rule:** Green pillars are passed on the left. Red pillars are passed on the right.

---

## Shutdown

When the run ends the robot:

1. Stops the motors
2. Centers the steering
3. Terminates the camera and vision processes
4. Releases and unlinks the shared memory block

---

[Open Challenge - Apostla 0.0.1 documentation](https://apostla-api-reference.web.app/open_challenge.html)

[Obstacle Challenge - Apostla 0.0.1 documentation](https://apostla-api-reference.web.app/obstacle_challenge.html)
