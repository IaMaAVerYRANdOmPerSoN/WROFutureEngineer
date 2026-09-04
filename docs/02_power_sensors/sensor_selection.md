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

We selected the OV5647 camera because it is the only sensor that can detect color, which is required for both the obstacle challenge (pillar colors) and the open challenge (corner line colors). The camera is also compact, lightweight, and fully supported by the `picamera2` library on Raspberry Pi OS (64-bit) Bookworm or later. The camera is elevated above the robot's body to give it a clear view of the track and obstacles.

While the single-sensor approach may have limitations, it simplifies the design and reduces cost, weight, and complexity. The camera is sufficient for all sensing tasks when combined with robust computer vision algorithms.
We considered adding a 2D LiDAR sensor, which can offer precise distance measurements, but introduces serial/I2C communication latency, extra CPU overhead for multi-sensor synchronization, and additional mass. Since monocular vision boundary tracking meets our positional accuracy requirements within our 62.5 FPS loop, adding distance sensors introduced unnecessary architectural complexity.

We also considered using the Pi Camera Module 3 Wide, which supports higher frame rates and resolutions, but is significantly more expensive and was not necessary for our current design. The OV5647 camera provides adequate performance for our needs at a lower cost. While the current camera is a performance bottleneck, our system does not operate at speeds where the frequency of the control loop is a limiting factor. Despite operating at the camera's maximum frame rate of 62.50 fps, the robot can still navigate the track effectively at the speeds required for the competition.

---

## Camera — OV5647

**Purpose:** The camera is the primary sensor for detecting everything color-dependent — colored pillars (red and green), corner lines (orange and blue), and walls (black).

**What it provides:** Raw image frames at 640x480 up to 62.50 fps, processed in HSV color space to detect objects by color and shape.

**Why it was selected:**

- The camera can distinguish colors, which is essential for both challenges
- CSI-2 interface provides lower latency than USB cameras
- Good support by the `picamera2` library on Raspberry Pi OS (64-bit) Bookworm or later
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
There aren't any perception problems that cannot be solved with a single camera in the context of our application, and while adding ToF or LiDAR sensors might improve performance in some aspects, it would also introduce new problems and increase the complexity of the system.
Adding LiDAR or ToF sensors would only be justified if there was a real constraint that the camera couldn't overcome, such as a requirement to detect objects in complete darkness. Since the camera is sufficient for our current design, we have chosen to keep the system simple and use only the camera.

---

## Trade-Offs

| Trade-Off | Decision |
| ----------- | ---------- |
| Cost vs performance | OV5647 chosen over Pi Camera Module 3, adequate performance at lower cost |
| Throughput vs Accuracy | Camera capped at 62.50 fps at 640x480, higher resolution reduces frame rate below what the control loop needs |
| Redundancy vs complexity | Single camera chosen, simplifies design and reduces weight, cost, and complexity |

---

## Final Decision

The OV5647 camera covers all sensing requirements for the competition. The camera is a lightweight, compact, and cost-effective solution that provides sufficient performance for both the open and obstacle challenges. While there are trade-offs in terms of accuracy and redundancy, the single-sensor approach simplifies the design and reduces potential points of failure.

---

## Arduino Uno R3

**Purpose:** Low-level hardware controller that handles PWM output to the ESC and servo, and receives drive commands from the Raspberry Pi over USB serial.

**Why it was selected:**
The Raspberry Pi 5 runs Linux, which is not a real-time operating system. It cannot guarantee microsecond-level PWM timing under load. When the vision pipeline and control loop are running at 62.5 fps, the CPU is busy enough that GPIO-based PWM timing becomes unreliable. The Arduino handles PWM output in a tight bare-metal loop with no operating system overhead, guaranteeing consistent pulse widths to the ESC and servo regardless of what the Pi is doing.

**Advantages:**
- Guarantees precise PWM timing independent of Pi CPU load
- Simple USB serial connection to the Pi
- Well-documented with broad library support for servo and ESC control
- Easy to flash and modify via PlatformIO
- Low cost and widely available

**Limitations:**
- Adds a serial communication step between the control loop and the hardware, introducing a small amount of latency
- Requires a separate USB cable and port on the Pi

**Alternatives considered:**
- **Direct Pi GPIO PWM** — unreliable under Linux without a dedicated real-time co-processor
- **ESP32** — more capable but significantly more complex to set up; overkill for this application
- **Hiwonder controller (used last year)**, replaced with the Arduino Uno for simpler software control and better documentation

---