# Config Details

[Back to Software Overview](../../README.md)

---

## Overview

All settings live in one global config object. Nothing is hardcoded — if you want to change a speed, a gain, or a color threshold, you change the config file, not the code. Once the robot starts, the config is locked and cannot be changed mid-run.

---

## The Config File

Edit `piclient.toml` in the root of the repo:

```toml
[CameraConfig]
OUTPUT_WIDTH = 512
OUTPUT_HEIGHT = 384

[OpenChallengeConfig]
WALL_FOLLOW_KPKD = [0.5, 0.0]
CORNER_TURN_KPKD = [1.0, 0.0]
MAX_SPEED = 0.4

[ClientConfig]
SERIAL_PORT = "/dev/ttyACM0"
```

---

## Override Priority

Settings can be changed in four ways. Higher in the list always wins:

| Priority | Method | Example |
|----------|--------|---------|
| 1 (highest) | CLI flag | `wro --CameraConfig.OUTPUT_WIDTH 640` |
| 2 | Environment variable | `WRO_CAMERACONFIG_OUTPUT_WIDTH=640` |
| 3 | piclient.toml | `OUTPUT_WIDTH = 640` |
| 4 (lowest) | Code defaults | Dataclass field values in config.py |

---

## What Can Be Configured

| Section | What it controls |
|---------|-----------------|
| `CameraConfig` | Resolution, format, frame rate |
| `ClientConfig` | Serial port for Arduino, baud rate |
| `VisionConfig` | HSV thresholds, ROI sizes, perspective transform |
| `OpenChallengeConfig` | PD gains, speed, turn detection thresholds, lap length |
| `ObstacleChallengeConfig` | PD gains for obstacle avoidance, pillar detection settings |
| `LiDARConfig` | Serial port for LiDAR |
| `GeneralConfig` | Which challenge to run (`open` or `obstacle`) |

---

[Lib - Apostla 0.0.1 documentation](https://apostla-api-reference.web.app/lib.html)

---

## Freeze

Once the robot starts, the config is frozen. Any attempt to change a value mid-run throws an error. This prevents accidental changes during a competition run.