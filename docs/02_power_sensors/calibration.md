# Calibration

[Back to README](../../README.md)


## Why Calibration Is Needed

- **Lighting variation** : competition lighting differs from home/practice lighting, which shifts what raw camera values correspond to each color
- **Manufacturing/mounting variation** : the ESC's throttle response and the camera's mounting angle vary slightly unit to unit
- **Sensor drift** : none of our current sensors drift meaningfully over a match, but color thresholds "drift" in practice whenever the venue changes
- **Measurement consistency** : the PD controller and vision pipeline both assume their tuned constants match the physical robot; if they don't, steering and object detection degrade

---

## Sensors/Actuators That Require Calibration

| Sensor/Actuator | What Is Calibrated | Why |
|--------|--------------------|-----|
| OV5647 camera | Color thresholds (UV-plane ranges per color, Y-plane ranges for black/white) | Raw pixel values for "red," "green," etc. shift with lighting conditions |
| OV5647 camera | Perspective transform (bird's-eye homography) | Converts the angled camera view to top-down coordinates for real-world distance estimates |
| Furitek Lizard Pro ESC | Throttle endpoints | Matches the ESC's PWM input range to the Arduino's output pulse range so commanded throttle produces expected torque |
| Control loop | PD gains (wall-follow, corner-turn, obstacle-avoid) | Tuned to the robot's actual mass, speed, and steering response rather than a generic starting value |

---

## Calibration Procedure for Camera Color Thresholds

- **Purpose:** Make the vision pipeline reliably classify walls (black/white), corner lines (orange/blue), and pillars (red/green) under the lighting the robot will actually run in.
- **Tools required:** Raspberry Pi with camera connected, `PiClient/utils` interactive tuning tools, laptop/monitor to view output.
- **Setup:** Place the robot on the actual competition mat (or as close a lighting match as possible), with the field elements (walls, corner lines, pillars) in frame.
- **Steps:**
    1. From `PiClient/`, run `python -m utils --tool contours contourbinary` to view the live camera feed with detected contours overlaid, plus a binary "clean blob" view.
    2. Compare detected regions against the real field elements. Under- or over-detected colors indicate thresholds are too narrow or too wide.
    3. Edit the relevant threshold constants in [`PiClient/src/config.py`](../../PiClient/src/config.py) — `LOWER_BLUE`/`UPPER_BLUE`, `LOWER_ORANGE`/`UPPER_ORANGE`, `LOWER_GREEN`/`UPPER_GREEN`, `LOWER_RED`/`UPPER_RED` (UV-plane ranges), and `LOWER_BLACK`/`UPPER_BLACK`, `LOWER_WHITE`/`UPPER_WHITE` (Y-plane ranges).
    4. Re-run the tool and repeat until detections are clean and stable across the frame.
- **Parameters measured:** UV-plane min/max per color; Y-plane min/max for black/white.
- **Parameters saved:** Hardcoded as constants in `Config.VisionConfig` in `PiClient/src/config.py` — there is currently no separate config file or persisted calibration profile.
- **When calibration is performed:** Before competition runs, whenever venue lighting changes noticeably, or after any camera/lens change.

---

## Calibration Procedure for Perspective Transform

- **Purpose:** Convert the camera's angled view into a bird's-eye view so pixel distances approximate real-world distances.
- **Tools required:** Camera view of the mat with known reference points, `VisionProcessor.get_perspective_transform()`.
- **Setup:** Place reference markers at known real-world coordinates within the camera's field of view.
- **Steps:**
    1. Identify four (or more) reference points visible in the camera frame with known real-world positions.
    2. Compute the homography matrix using `VisionProcessor.get_perspective_transform()`.
    3. Set `Config.VisionConfig.PERSPECTIVE_TRANSFORM` in `PiClient/src/config.py` to the resulting matrix.
- **Parameters measured:** Pixel coordinates of reference points and their corresponding real-world coordinates.
- **Parameters saved:** 3x3 homography matrix in `Config.VisionConfig.PERSPECTIVE_TRANSFORM`.
- **When calibration is performed:** Currently **not performed** — `PERSPECTIVE_TRANSFORM` is still a placeholder of zeros. For Open Challenge, wall-following only needs relative left/right wall distance, not true metric distance, so the current plan is to bypass this transform for Open Challenge rather than spend time calibrating it. It remains open for Obstacle Challenge if metric distance estimation becomes necessary.

---

## Calibration Procedure for ESC Throttle Range

- **Purpose:** Match the Furitek Lizard Pro ESC's expected PWM pulse range to the pulse range the Arduino actually outputs, so a given throttle command produces consistent, expected torque.
- **Tools required:** Furitek Lizard Pro ESC, Arduino Uno R3, battery, motor.
- **Setup:** Motor and battery connected, robot safely elevated so wheels can spin freely.
- **Steps:**
    1. Follow the ESC manufacturer's calibration procedure (typically: power on with throttle at max, then min, to record endpoints).
    2. Verify the neutral/stop pulse (1500µs, per [`ArudinoServer/src/main.cpp`](../../ArudinoServer/src/main.cpp)) is recognized as "stop" by the ESC.
    3. Test throttle at the operating range used in code (30-40%, per [torque_speed_reasoning.md](../01_mechanical/torque_speed_reasoning.md)) and confirm torque output matches expectations.
- **Parameters measured:** Min/max/neutral PWM pulse widths recognized by the ESC.
- **Parameters saved:** Stored internally by the ESC itself (not in our codebase). The Arduino firmware's output range must stay within what the ESC was calibrated to accept.
- **When calibration is performed:** After any ESC replacement or reset, or if throttle response feels inconsistent with commanded speed. An uncalibrated ESC previously caused a loss of torque at expected throttle values.

---

## Calibration Procedure for PD Controller Gains

- **Purpose:** Tune steering response (wall-following, corner-turning, obstacle-avoidance) to the robot's actual handling characteristics.
- **Tools required:** Assembled robot on the track, `PiClient/utils` control diagnostics tool.
- **Setup:** Robot placed on a straight or cornered section of track matching the behavior being tuned.
- **Steps:**
    1. Run `python -m utils --tool control` to view a live overlay of the current P/D values for each mode.
    2. Run the robot and observe steering behavior (oscillation, overshoot, sluggish correction).
    3. Adjust `WALL_FOLLOW_KPKD`, `CORNER_TURN_KPKD`, and `OBSTACLE_AVOID_KPKD` in `Config.OpenChallengeConfig`/`Config.ObstacleChallengeConfig` in `PiClient/src/config.py`.
    4. Re-test until steering is stable without excessive oscillation.
- **Parameters measured:** Qualitative steering behavior (oscillation, response lag).
- **Parameters saved:** `(Kp, Kd)` tuples per mode, hardcoded in `PiClient/src/config.py`.
- **When calibration is performed:** After any change to robot weight, wheel/tire grip, gear ratio, or speed settings.

---

## Example Calibration Results

| Sensor | Parameter | Before | After | Notes |
|--------|-----------|--------|-------|-------|
| Camera | Green pillar UV threshold | Detected under indoor fluorescent light only | Widened range to also catch competition venue lighting | Re-tuned on-site before competition |
| ESC | Throttle response | Torque loss at expected throttle values | Full expected torque restored | Root cause was a missed ESC calibration step, not a code issue |

---

## Calibration Storage

- **Where calibration values are stored:** Directly as hardcoded constants in [`PiClient/src/config.py`](../../PiClient/src/config.py) (`Config.VisionConfig`, `Config.OpenChallengeConfig`, `Config.ObstacleChallengeConfig`). ESC endpoint calibration is stored internally by the ESC hardware itself.
- **How they are loaded:** Imported directly as Python class attributes wherever `Config` is used — no external config file is read at runtime.
- **How calibration is verified:** Visually, using the `utils` diagnostic tools (`contours`, `contourbinary`, `control`) before a run. There is currently no automated verification or saved calibration profile, this is a known gap.

---

## Common Calibration Issues

- Thresholds tuned indoors under one lighting setup don't transfer to competition lighting
- Corner line and pillar colors can look similar under certain lighting if thresholds are too wide
- An uncalibrated ESC silently reduces torque without any error, it can look like a code or gearing problem
- PD gains tuned for one speed setting can cause oscillation if speed is changed later without re-tuning
- No persisted calibration file means values can be accidentally overwritten or lost if `config.py` changes are not tracked carefully

---

## Final Notes

All current calibration is manual: thresholds and gains are tuned by eye against a live camera/diagnostic overlay and then hardcoded into `config.py`, rather than measured and saved through an automated or file-based calibration step. This is fast to iterate on but fragile, it must be redone at every venue with different lighting, and there's no way to verify at startup that the robot is still correctly calibrated. Formalizing this (e.g., a saved calibration file loaded at startup, with a quick on-site verification routine) is a planned improvement.
