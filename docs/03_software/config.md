# Config Details

[Back to Software Overview](../../README.md)

---

## Overview

All settings live in the global [`Config`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config) object returned by [`GLOBAL_CONFIG()`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.GLOBAL_CONFIG). Nothing is hardcoded — if you want to change a speed, a gain, or a color threshold, you change the config file, not the code. Once the robot starts, the config is locked and cannot be changed mid-run.

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
| -------- | ------ | ------- |
| 1 (highest) | CLI flag | `wro --CameraConfig.OUTPUT_WIDTH 640` |
| 2 | Environment variable | `WRO__CAMERACONFIG__OUTPUT_WIDTH=640` |
| 3 | piclient.toml | `OUTPUT_WIDTH = 640` |
| 4 (lowest) | Code defaults | Dataclass field values in config.py |

---

## What Can Be Configured

| Section | What it controls |
| ------- | ---------------- |
| [`CameraConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.CameraConfig) | Resolution, format, frame rate |
| [`ClientConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.ClientConfig) | Serial port for Arduino, baud rate |
| [`VisionConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.VisionConfig) | HSV thresholds, ROI sizes, perspective transform |
| [`OpenChallengeConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.OpenChallengeConfig) | PD gains, speed, turn detection thresholds, lap length |
| [`ObstacleChallengeConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.ObstacleChallengeConfig) | PD gains for obstacle avoidance, pillar detection settings |
| [`LiDARConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.LiDARConfig) | Serial port for LiDAR |
| [`GeneralConfig`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Config.GeneralConfig) | Which challenge to run (`open` or `obstacle`), logging level |

---

[Lib - Apostla 0.0.1 documentation](https://apostla-api-reference.web.app/lib.html)

---

## Freeze

Once the robot starts, the config is frozen with [`Freezeable.freeze()`](https://apostla-api-reference.web.app/lib.html#piclient.core.lib.Freezeable.freeze). Any attempt to change a value mid-run throws an error. This prevents accidental changes during a competition run.
