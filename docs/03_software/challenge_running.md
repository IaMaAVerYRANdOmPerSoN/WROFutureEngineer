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

## How Vision and the State Machine Work Together

The vision process and the state machine run as separate processes but are tightly coupled through a pipe. Every camera frame produces a set of measurements — wall distances, pillar positions, corner fill — and these measurements are what the state machine acts on.

The key relationship is:

- **Vision tells the state machine what it sees.** It does not make decisions — it only reports numbers.
- **The state machine decides what to do with those numbers.** It evaluates the measurements against thresholds, applies hysteresis, and chooses a state.
- **The state determines which drive command gets sent.** Different states use different PD gains and speeds.
This separation means the vision code can be tested independently using a recorded video, and the state machine logic can be reasoned about without worrying about how the measurements were produced.

---

## How HSV Detection Works

The camera captures frames in BGR format. Before any detection is done, each frame is converted to HSV (Hue, Saturation, Value) color space. HSV separates color information from brightness, which makes detection more stable under different lighting conditions — a red pillar in shadow still has roughly the same hue and saturation, only its value changes. We swap the B and R channels to avoid maintaining two thresholds for red, since red wraps around the hue wheel at both 0° and 180°. The OpenCV `inRange` function is used to create binary masks for each color of interest.
**Walls** are detected by masking for black pixels — low value, low saturation. The amount of black in the left, right, and center regions of the frame is counted and used as a proxy for wall distance.
**Pillars** are detected by masking for red and green:

- **Green** sits around hue 40–80 in OpenCV's 0–180 scale. A single mask covers the full green range.
- **Red** is swapped to the blue channel, so it sits around hue 0–20. A single mask covers the full red range.

```python
mask_green = cv2.inRange(hsv, lower_green, upper_green)
mask_red = cv2.inRange(hsv, lower_red, upper_red)
```

Once masked, contours are found and the largest one is taken as the detected pillar. The position of that contour relative to the nearby wall determines the steering target.

All HSV threshold values are set in `piclient.toml` under `[VisionConfig]` and should be tuned under competition lighting before each run.

---

## Obstacle Challenge

### [`StateMachine`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.StateMachine)

Introduces `obstacle_avoid` and `parallel_parking` states.

| State | What triggers it | What the robot does |
| ----- | ---------------- | ------------------- |
| Straight | Default | Wall follow using [`PD`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.PD) controller |
| Turn | Corner detected | Hard steer toward missing wall |
| Obstacle Avoid | Vision returns a pillar target | Steers toward the gap between pillar and wall |
| Parallel Parking | Vision returns a parking lot target and the 3rd lap is complete | Steers toward the parking lot and executes a parallel parking maneuver |

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
