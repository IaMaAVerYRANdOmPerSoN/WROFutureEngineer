# Vision Details

[Back to Software Overview](../../README.md)

---

## Overview

The vision pipeline reads camera frames and works out where the walls and obstacles are. It runs inside the vision process so it does not slow down the main control loop.

All frames are converted from BGR to HSV before any detection is done. HSV separates color from brightness, which makes detection more reliable under different lighting conditions.

---

## Open Challenge

For the open challenge there are no obstacles — just walls.

The vision code looks at three regions of the frame:
- **Left ROI** — counts black pixels on the left side
- **Right ROI** — counts black pixels on the right side
- **Center ROI** — counts black pixels straight ahead

More black pixels in a region means the wall is closer. The difference between left and right is fed into the PD controller to keep the robot centered between the walls.

**Corner detection:** When the center ROI fills up with black pixels, a wall is straight ahead. This triggers a corner turn after being confirmed over several consecutive frames.

---

## Obstacle Challenge

The obstacle challenge adds red and green pillars to the track.

**Wall detection:** Walls are found as contours rather than pixel counts. The distance is measured as the gap between the wall's bounding box and the frame center.

**Pillar detection:**
- The frame is masked for red and green HSV ranges separately
- The largest contour in each mask is taken as the detected pillar
- Red requires two HSV masks because red wraps around the hue wheel (0° and 180°)

**Steering target:** The code finds the shortest gap between the detected pillar and the nearest wall. The midpoint of that gap becomes the steering target for the avoidance maneuver.

**WRO rule:** Green pillars must be passed on the left. Red pillars must be passed on the right.

---

## HSV Color Ranges

All thresholds are set in `piclient.toml` under `[VisionConfig]`. Tune these under competition lighting before a run using the tools in `utils/`.

| Color | Notes |
|-------|-------|
| Black (walls) | Low value, low saturation |
| Red (pillars) | Two ranges needed due to hue wrap-around |
| Green (pillars) | Single range around hue 40–80 |

---

## Tuning Tools

The `utils/` folder has interactive tools for tuning vision settings:

```bash
python -m utils --tool contours control
```

This opens live OpenCV windows where you can adjust HSV thresholds, ROI sizes, and see contours in real time without restarting the robot.

> **Note:** The utils tools currently have outdated imports. Update any `from src.core.*` imports to `from piclient.core.*` before running.