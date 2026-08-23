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

Our robot only uses a single sensor: An OV5647 camera with a wide angle lens. The camera is mounted on the front of the robot, facing forward, and captures frames at 640x480 resolution at up to 62.50 fps. The camera is the only data source for our system, and it is used for all sensing tasks. The camera's raw BGR arrays are first converted to HSV color space, then fed to downstream pipelines for object detection.

We selected the OV5647 camera because it is the only sensor that can detect color, which is required for both the obstacle challenge (pillar colors) and the open challenge (corner line colors). The camera is also compact, lightweight, and fully supported by the `picamera2` library on Raspberry Pi OS Bullseye or later. The camera is elevated above the robot's body to give it a clear view of the track and obstacles.

While the single-sensor approach may have limitations, it simplifies the design and reduces cost, weight, and complexity. The camera is sufficient for all sensing tasks when combined with robust computer vision algorithms.
We considered adding a 2D LiDAR sensor to improve wall distance measurement, but it did not solve any existing problems and would have presented additional integration challenges.

We also considered using the Pi Camera Module 3 Wide, which supports higher frame rates and resolutions, but it is significantly more expensive and was not necessary for our current design. The OV5647 camera provides adequate performance for our needs at a lower cost. The current camera is a performance bottleneck, but our system does not operate at speeds where the frequency of the control loop is a limiting factor. Despite only operating at the camera's maximum frame rate of 62.50 fps, the robot can still navigate the track effectively at the speeds required for the competition.

---

## Camera — OV5647

**Purpose:** The camera is the primary sensor for detecting everything color-dependent — colored pillars (red and green), corner lines (orange and blue), and walls (black).

**What it provides:** Raw image frames at 640x480 up to 62.50 fps, processed in HSV color space to detect objects by color and shape.

**Why it was selected:**

- The camera can distinguish colors, which is essential for both challenges
- CSI-2 interface provides lower latency than USB cameras
- Good support by the `picamera2` library on Raspberry Pi OS Bullseye or later
- Lightweight and compact

**Advantages:**

- Can detect multiple instances of different object types in a single frame
- No external power required beyond the Pi's CSI port
- Fine-grained control over resolution, frame rate, exposure, and other camera settings through `picamera2`
- Easy to process data with mature scientific Python libraries like OpenCV and NumPy

**Limitations:**

- Performance degrades under poor or inconsistent lighting
- Requires HSV threshold tuning under competition lighting conditions
- Cannot measure distance directly; Distance must be inferred from pixel counts or object sizes, which is less reliable than direct distance measurements

**Alternatives considered:**

- **USB webcam** — higher latency due to USB overhead, more bandwidth contention with Arduino
- **Pi Camera Module 3 Wide** — supports 120 fps at higher resolution, but significantly more expensive; considered as a future upgrade

---

## Single Sensor Approach

It's easy to underestimate the difficulty of process/thread synchronization and data fusion when multiple sensors are used. At the same time, multiple sensors can provide redundancy and improve accuracy.
It's a complex trade-off between cost, weight, complexity, and performance. Historically, a single camera has been sufficient for WRO FE robots, and we expect it to be sufficient for our robot as well.
There isn't any problem that is strictly unsolvable with a single camera, and while adding ToF or LiDAR sensors might improve performance in some aspects, it would also introduce new problems and increase the complexity of the system.
Adding LiDAR or ToF sensors would only be justified if there was a real constraint that the camera couldn't overcome, such as a requirement to detect objects in complete darkness. Since the camera is sufficient for our current design, we have chosen to keep the system simple and use only the camera.

---

## Trade-Offs

| Trade-Off | Decision |
| ----------- | ---------- |
| Cost vs performance | OV5647 chosen over Pi Camera Module 3 — adequate performance at lower cost |
| Weight vs functionality | OV5647 chosen over Pi Camera Module 3 — lighter weight while maintaining necessary functionality |
| Throughput vs Accuracy | Camera capped at 62.50 fps at 640x480 — higher resolution reduces frame rate below what the control loop needs |
| Redundancy vs complexity | Single camera chosen — simplifies design and reduces weight, cost, and complexity |

---

## Final Decision

The OV5647 camera covers all sensing requirements for the competition. The camera is a lightweight, compact, and cost-effective solution that provides sufficient performance for both the open and obstacle challenges. While there are trade-offs in terms of accuracy and redundancy, the single-sensor approach simplifies the design and reduces potential points of failure.