# Sensor Selection

[Back to README](../../README.md)

This document explains which sensors were selected for the robot, why they were chosen, and what alternatives were considered.

---

## Sensing Requirements

The robot needs to:
- Detect walls and stay centered between them
- Identify colored pillars (red and green) and pass on the correct side
- Detect corner lines to know when to turn
- Count laps to know when to stop
- Detect the parking lot for the obstacle challenge

---

## Sensor Summary

| Sensor | Purpose | Why Chosen | Alternatives Considered |
|--------|---------|------------|--------------------------|
| OV5647 Camera | Color detection, wall and pillar detection, corner line detection | Lightweight, CSI-2 interface for low latency, well supported by picamera2 | USB webcam, Pi Camera Module 3 |
| LD19 LiDAR | 360-degree distance measurement for wall detection | Lighting-independent, precise, wide field of view | Ultrasonic sensors, IR distance sensors |

---

## Camera — OV5647

**Purpose:** The camera is the primary sensor for detecting everything color-dependent — colored pillars (red and green), corner lines (orange and blue), and walls (black).

**What it provides:** Raw image frames at 640x480 up to 62.50 fps, processed in HSV color space to detect objects by color and shape.

**Why it was selected:**
- Only sensor capable of distinguishing color, which is required for both the obstacle challenge pass direction and the open challenge turn direction
- CSI-2 interface provides lower latency than USB cameras
- Well supported by the `picamera2` library on Raspberry Pi OS
- Lightweight and compact

**Advantages:**
- Can detect multiple object types in a single frame
- High frame rate at the resolution we need
- No external power required beyond the Pi's CSI port

**Limitations:**
- Performance degrades under poor or inconsistent lighting
- Requires HSV threshold tuning under competition lighting conditions
- Cannot measure distance directly

**Alternatives considered:**
- **USB webcam** — higher latency due to USB overhead, more bandwidth contention with Arduino and LiDAR
- **Pi Camera Module 3 Wide** — supports 120 fps at higher resolution, but significantly more expensive; considered as a future upgrade

---

## LiDAR — LD19

**Purpose:** The LiDAR provides precise 360-degree distance measurements used to detect walls and measure lateral distance from the robot to each side.

**What it provides:** A full 360-degree sweep of distance readings at roughly 5–10Hz, parsed from binary packets into polar coordinates and converted to Cartesian.

**Why it was selected:**
- Completely unaffected by lighting conditions, unlike the camera
- Provides reliable distance data to both walls simultaneously in a single scan
- Compact and lightweight for its capability
- Simple USB serial interface

**Advantages:**
- Works in any lighting condition
- Provides distance to both walls at once
- Does not require color calibration

**Limitations:**
- Cannot detect color — cannot distinguish pillar colors or corner line colors
- Not yet integrated into the challenge runners; currently parsed but unused in control logic
- Lower update rate compared to the camera

**Alternatives considered:**
- **Ultrasonic sensors** — only measure in a single direction; would need multiple sensors to cover both walls, adding wiring and processing complexity
- **IR distance sensors** — narrow field of view, affected by surface color and reflectivity

---

## Sensor Combination Strategy

No single sensor is sufficient on its own:

- The **camera alone** cannot reliably measure wall distance — pixel counting is an approximation affected by lighting and perspective
- The **LiDAR alone** cannot detect color — it cannot identify pillar colors or corner line direction

Together they cover each other's weaknesses. The LiDAR handles precise, lighting-independent wall distance measurement. The camera handles all color-dependent detection — pillars, corner lines, and starting direction.

| Task | Primary Sensor |
|------|---------------|
| Wall following | LiDAR (planned) / Camera (current) |
| Corner detection | Camera |
| Pillar detection | Camera |
| Starting direction | Camera |
| Parking lot detection | Camera / LiDAR |

---

## Trade-Offs

| Trade-Off | Decision |
|-----------|----------|
| Cost vs performance | OV5647 chosen over Pi Camera Module 3 — adequate performance at lower cost |
| Accuracy vs complexity | LiDAR chosen over multiple ultrasonic sensors — single sensor, simpler wiring, better accuracy |
| Range vs mounting | LiDAR mounted on top of robot for full 360-degree field of view despite raising the center of gravity |
| Update rate vs processing | Camera capped at 62.50 fps at 640x480 — higher resolution reduces frame rate below what the control loop needs |

---

## Final Decision

The OV5647 camera and LD19 LiDAR together cover all sensing requirements for the competition. The camera handles everything color-related, and the LiDAR handles precise distance measurement independently of lighting. Both are compact, lightweight, and compatible with the Raspberry Pi 5 without additional interface hardware.