# Hardware Interface Details

[Back to Software Overview](../../README.md)

---

## Camera

The camera runs in its own process using the Raspberry Pi `picamera2` library. Since `picamera2` is a blocking library, captures are run on a thread pool so the async event loop stays responsive.

Each frame is written directly into shared memory using a zero-copy method (`np.copyto`). The vision process reads from the same shared memory block without any additional copying. A pipe signal tells the vision process when a new frame is ready.

**Config options:** resolution, format, and frame rate are all set in `piclient.toml` under `[CameraConfig]`.

---

## Arduino Client

The Arduino is connected over USB serial. The client (`piclient.core.interface.drive.client`) sends text commands and receives responses asynchronously.

Each command is assigned a transaction ID (TID). A background listener reads every response line and matches it to the correct pending command by TID. This means multiple commands can be sent without waiting for a response first.

**Main commands:**

| Command | What it does |
|---------|-------------|
| `verify_connection` | PING/PONG handshake to confirm the Arduino is connected |
| `set_servo_angle` | Sets steering angle (clamped 0–180°) |
| `set_motor_speed` | Sets drive speed (normalized −1 to 1) |
| `drive_motors` | Sets both speed and angle at the same time |

**Back-pressure handling:** If the Arduino replies with `WAITMS <ms>`, the client waits the requested time before retrying. This prevents the Pi from overwhelming the Arduino.

The serial port is set in `piclient.toml` under `[ClientConfig]`.

---

## DriveCommandExecutor

The DriveCommandExecutor sits between the fast control loop and the slower serial link. The control loop can call `submit(speed, angle, duration)` every frame without ever waiting for the Arduino to respond.

Internally, the executor stores only the latest command. A single background worker sends it to the Arduino when the serial link is free. If a new command arrives before the old one is sent, the old one is overwritten. Stale commands are never sent.

This is what allows the control loop to run at full frame rate without stalling on serial latency.

---

## LiDAR

The LiDAR interface parses binary 47-byte packets from the LD19 LiDAR sensor, converts polar coordinates to Cartesian, and exposes them as structured data.

**Current status:** The LiDAR is wired up and the parsing code works, but it is not yet connected to either the open challenge or obstacle challenge runner. It is available as future work. A tuning tool also exists in `utils/` but currently raises `NotImplementedError`.

---

[Interface - Apostla 0.0.1 documentation](https://apostla-api-reference.web.app/interface.html)