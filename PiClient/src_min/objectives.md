# Goals

## Coding Objectives: 
- Refactor all modules in src_min to drop async and multiprocessing and multithreading, and instead use a single-threaded, synchronous design.
- KISS, discard two months of work because I am a fucking idiot that overengineered everything and can't stop myself from doing it.

Okay here's the notes from coach :sob: (I liked the fancy stuff):

> 1) The architecture is significantly over-engineered for open challenge.
> This codebase uses async/await, multiprocessing with shared memory, inter-process pipes, thread pool executors, a transaction-ID-based serial protocol, and structured logging — all for a robot that needs to follow walls and turn corners. While the engineering is impressive, the complexity introduces many failure points and makes debugging on competition day very difficult. It is like shooting a fly with a missile.
>
> `__init__.py` — Entry point. Parses command-line args (debug/verbose/test modes), configures logging with loguru, and calls asyncio.run(run()) to start the robot.  
> `asyncCamera.py` — Wraps PiCamera2 in an async context manager. Captures YUV420 frames, crops the top ROI, upscales the UV planes, and writes the result into shared memory for other processes to read.  
> `commProtocol.py` — Async serial client for Arduino communication. Each command gets a transaction ID, and a background listener matches responses to pending requests. Exposes high-level methods like set_servo_angle, set_motor_speed, and drive_motors.  
> `controller.py` — A simple PD controller class. Takes an error, returns a correction value using proportional and derivative terms.  
> `open_challenge.py`— The main control loop. Launches camera and vision as separate processes, then runs a two-state machine ("Follow wall" / "Turn") that reads vision data and sends drive commands.  
> `visionProcessing.py`— All computer vision logic. Detects walls (black), obstacles (green/red), corner lines (orange/blue), and field boundaries (white) using color thresholding in YUV space. Computes distances and centroids. The async subclass wraps everything in executor threads for use with multiprocessing.  
>
> In principle, don't pay for complexity until you need what it buys!
> You have limited debugging time, the robot needs to work on competition day, and the team members need to understand every line of code.
> A solution that every team member can read, debug, and modify under pressure beats an elegant but complex one.
>
> Here's what I'd suggest: keep the multi-file structure but drop the async/multiprocessing complexity.
> The Raspberry Pi is processing one camera frame at a time in a sequential loop — there's no real concurrency benefit here since everything depends on the latest frame.
> The only thing you could possibly gain using "async" is you could start capturing the next frame while sending the serial command - but that's negligible compared to the simplicity you gain.
>
> Suggested structure:
> `main.py`              # Entry point, main loop, state machine
> `camera.py`            # Camera init and frame capture (thin wrapper)
> `vision.py`            # Color detection, wall areas, line detection
> `comm.py`              # Serial communication with Arduino
> `controller.py`        # PD controller (already good as-is)
> `config.py`            # All tunable constants in one place
>
> Each module is a plain synchronous class or set of functions. No async, no multiprocessing, no shared memory, no thread pools. The main loop calls them in sequence.
>
> ## main.py — simplified
>
> ```python
> from camera import Camera
> from vision import Vision
> from comm import Arduino
> from controller import PD
> import config
>
> camera = Camera()
> arduino = Arduino()
> vision = Vision()
> wall_pd = PD(config.KP, config.KD)
>
> state = "WALL_FOLLOW"
> turn_count = 0
>
> try:
>     while state != "FINISHED":
>         frame = camera.get_frame()
>         walls = vision.get_wall_areas(frame)
>         lines = vision.get_corner_lines(frame)
>
>         if state == "WALL_FOLLOW":
>             # PD steering, check for corner entry
>             ...
>         elif state == "CORNER_TURN":
>             # Fixed or guided turn, check exit conditions
>            ...
>
> finally:
>     arduino.stop()
>     camera.close()
> ```
>
> Why this works better than async for the open challenge:
> The robot's control loop is inherently sequential — you capture a frame, process it, decide what to do, send a command, repeat. Async shines when you're waiting on multiple independent I/O sources (e.g., a web server handling many clients). Here, every step depends on the previous one. The camera frame must be captured before vision can process it, and vision results must be ready before the controller can act. Async adds overhead and complexity without enabling any real parallelism.
>
> There are other issues in the current implementation. However, many of them simply disappear when you remove async and multiprocessing entirely.
> No point fixing plumbing in a building you're redesigning.
>
> For obstacle challenge, you may use camera, 2D LiDAR, IMU together. That's where async and multiprocessing start to pay off.

## Mechanical Objectives: 

List of things to improve but not big enough to print a new part for:

> - Add a place to screw in voltage regulator
> - Make camera angle more downwards
> - Create a spot to put switch
> - Create a Lidar holder + make space for it
> - Fix differential gear issue
