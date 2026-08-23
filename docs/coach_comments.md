# April 8th
```
I agree with Michael that you can overlapping image grabbing and image processing to increase the overall throughput. For example, while you're processing frame N, the camera hardware can be capturing frame N+1. By the time processing finishes, the next frame is already ready. The decision really depends on what frame rate you need. For Open Challenge wall following, 30fps is likely plenty. Even with sequential capture + processing, we can keep up with the full 30 fps. But if you're doing Obstacle Challenge and need fast reaction to pillars/parking lots, larger fps (e.g. 60) with overlapped capture/processing could make a real difference.
Example #1: 30fps Open Challenge
Frame interval: 33ms. Assume capture takes 15ms. Processing takes 15ms.
Sequential: 15 + 15 = 30ms. That's under 33ms, so you finish and wait 3ms idle for the next frame. Your effective rate is 30fps — the camera is the bottleneck, not your code.
Overlapped: ~15ms per cycle. But you still can't get a new frame faster than every 33ms. So you finish in 15ms and wait 18ms idle. Still 30fps.
Either way you get 30fps. Overlapping just increases your idle time. It doesn't help.
Example #2: 60fps Obstacle Challenge
Frame interval: 16.7ms. Assume capture takes 15ms. Processing takes 15ms.
Sequential: 15 + 15 = 30ms. That exceeds 16.7ms, so you can only process one frame every 30ms, dropping your effective rate to ~33fps (1000/30) instead of 60fps. You're processing every second frame while one goes to waste in between.
Overlapped: While processing frame N (15ms), frame N+1 is being captured simultaneously. Processing finishes in 15ms, which is under 16.7ms, so the next frame is ready. You keep up with the full 60fps.
The rule:
Overlapping only matters when capture + processing > frame interval. At 30fps (33ms interval), 15+15=30 fits. At 60fps (16.7ms interval), 15+15=30 doesn't fit — that's when overlapping saves you.
```
# April 11th


```
 1) The architecture is significantly over-engineered for open challenge.
 This codebase uses async/await, multiprocessing with shared memory, inter-process pipes, thread pool executors, a transaction-ID-based serial protocol, and structured logging — all for a robot that needs to follow walls and turn corners. While the engineering is impressive, the complexity introduces many failure points and makes debugging on competition day very difficult. It is like shooting a fly with a missile.

 __init__.py — Entry point. Parses command-line args (debug/verbose/test modes), configures logging with loguru, and calls asyncio.run(run()) to start the robot.
 asyncCamera.py — Wraps PiCamera2 in an async context manager. Captures YUV420 frames, crops the top ROI, upscales the UV planes, and writes the result into shared memory for other processes to read.
 commProtocol.py — Async serial client for Arduino communication. Each command gets a transaction ID, and a background listener matches responses to pending requests. Exposes high-level methods like set_servo_angle, set_motor_speed, and drive_motors.
 controller.py — A simple PD controller class. Takes an error, returns a correction value using proportional and derivative terms.
 open_challenge.py— The main control loop. Launches camera and vision as separate processes, then runs a two-state machine ("Follow wall" / "Turn") that reads vision data and sends drive commands. 
 visionProcessing.py— All computer vision logic. Detects walls (black), obstacles (green/red), corner lines (orange/blue), and field boundaries (white) using color thresholding in YUV space. Computes distances and centroids. The async subclass wraps everything in executor threads for use with multiprocessing.

 In principle, don't pay for complexity until you need what it buys!
 You have limited debugging time, the robot needs to work on competition day, and the team members need to understand every line of code.
 A solution that every team member can read, debug, and modify under pressure beats an elegant but complex one.

 Here's what I'd suggest: keep the multi-file structure but drop the async/multiprocessing complexity.
 The Raspberry Pi is processing one camera frame at a time in a sequential loop — there's no real concurrency benefit here since everything depends on the latest frame.
 The only thing you could possibly gain using "async" is you could start capturing the next frame while sending the serial command - but that's negligible compared to the simplicity you gain.

 Suggested structure:
 main.py              # Entry point, main loop, state machine
 camera.py            # Camera init and frame capture (thin wrapper)
 vision.py            # Color detection, wall areas, line detection
 comm.py              # Serial communication with Arduino
 controller.py        # PD controller (already good as-is)
 config.py            # All tunable constants in one place

 Each module is a plain synchronous class or set of functions. No async, no multiprocessing, no shared memory, no thread pools. The main loop calls them in sequence.


```

# April 15th

```
1) Color Space — YUV 
Working in native YUV420 avoids a cvtColor call every frame. Thus make image processing faster.
Color detection thresholds use only U and V channels (frame[:, :, 1:3]), which correctly ignores brightness.
However, UV thresholds might be less intuitive to re-tune at competition, where lighting condition is different.

Suggestion: 
LAB is most robust under different lighting conditions.
Have a fallback plan of LAB space.


2) Camera.py
Many hardcoded numbers: 512*384, 256*192, and INITIAL_ROI = 100. 
Suggestion: Put them in config.py

3) controller.py
Suggestion: reset previous_error to 0 when switching states

4) visionProcessing.py
Suggestion: No need to process RED and Green for open challenge

5) State transition
Corner lines appear → enter Turn. Corner lines disappear → back to Follow wall. That's it — purely based on whether orange/blue lines are detected in the current frame.
It doesn't explicitly decide "turn left" or "turn right." It chases the largest corner line's centroid, steering to keep it at the frame center (192 pixels). 
The sign of x_centroid - 192 determines the steering direction — line to the left of center gives negative correction, line to the right gives positive correction.

Potential issues
Corner line color is ignored. Orange means CW, blue means CCW. The code doesn't check corner_lines[0].color at all. 
It just follows wherever the line happens to appear in the frame. This could work accidentally if the line position correlates with the correct turn direction, but it's not reliable.

The exit condition is too early. The robot switches back to "Follow wall" the moment corner lines leave the frame. 
But the line might disappear while the robot is still mid-turn — it hasn't completed 90° yet, and the walls haven't reappeared. 
The robot returns to wall following without walls visible, gets inf distances, and produces garbage output.

The entry condition can be too late. If the camera doesn't detect corner lines reliably (lighting, threshold issues), 
the robot stays in "Follow wall" while entering a corner. One wall disappears, wall_x_diffs goes to inf, and the PD controller breaks.

Single-frame detection is fragile. A momentary false positive (noise detected as a corner line) flips the state to Turn. 
A momentary false negative (corner line missed for one frame) flips it back to Follow wall mid-corner. There's no hysteresis or confirmation — one frame decides the state.

Suggestion:
Enter Turn when corner lines appear or one wall disappears
Use the corner line color to set a fixed turn direction
Stay in Turn until both walls are visible again, not until corner lines disappear
Require several consecutive frames before switching states, to filter noise

6) No lap counting
The robot runs forever — there's no counter tracking corner lines to stop after 3 laps (12 corners).

7) inf wall distances break the PD controller. 
get_wall_distance returns float("inf") when a wall isn't detected, and the PD controller computes inf - inf = NaN or inf - number = inf. 
This will produce garbage steering commands even in "Follow wall" state if a wall is momentarily missed. It needs an explicit guard.

8) Same speed in both states.
Suggestion: User slower speed for corner turn

9) aioserial imported but used synchronously. 
The code calls self.SERIAL.write() and self.SERIAL.readline() — the sync methods. Regular pyserial would be simpler and avoids an unnecessary dependency.

10) A perspective transform converts the camera's angled view into a bird's-eye (top-down) view.
src = np.array([
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
], dtype=np.float32)
dst = np.array([
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
], dtype=np.float32)

This is placeholder code that needs to be filled in with real calibration values.

The question is whether it's needed. It takes time to calibrate in a new environment.
For Open Challenge, wall following just needs to know "am I closer to the left wall or the right wall?" 
Bounding box positions in the raw camera view answer that fine — perspective distortion doesn't change which wall is closer. 
The distances won't be proportional to real centimeters, but the PD controller doesn't care about absolute distance, only the relative error between left and right.

Suggestion: bypass perspective transform for Open Challenge
```