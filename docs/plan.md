# Plan
## 2026-02-05
~~First Commit~~

## 2026-03-05
### Finish Robot Chassis - Elvis
1. ~~Finish differential gear~~
2. ~~Finish implementing last years turning system~~
3. ~~Map out layout of where everything should go~~
4. Design a way to hold everything together
5. Assemble everything

### Finish custom PCB - Michael
1. ~~Validate schematic.~~
2. ~~Finish footprint placement in board editor.~~
3. ~~Send order to the FAB and run physical tests.~~

## 2026-04-05
### Open Challenge Completed - Michael, Elvis
1. Create `VisionTuning.py`, a GUI that takes a video file or live frames and provides easy tuning for color ranges.
2. Finish Unittests
    - ~~`camera.py`, validating asynchronous wrapper for the `PiCamera2` Library found in `AsyncCamera.py`.~~
    - ~~`RPC.py`, testing the asynchronous two-way Remote Procedure Call between the Raspberry Pi 5 and Arduino.~~
    - `Vision.py`, A vision processing test that integrates `AsyncCamera` and `AsyncVisionProcessor`, utilizing multiprocessing and shared memory.
    - `turning.py`, integrating sensors to corner.
3. Develop main file `OpenChallenge.py`.
4. Run integration tests and tune `OpenChallenge.py`.

### Documentation - Ryan
1. Create design journal and document engineering process.
2. Justify design and show compatibility tests.
3. Full API reference for `asyncCamera`, `commProtocol`, `controller` and `visionProcessing` modules.

## 2026-05-05
## 2026-06-05
## 2026-07-05
## 2026-08-05
### Finish Obstacle Challenge - Michael, Elvis
1. Run Unittests
    - `obstacleDetection.py`, validating obstacle detection and location.
    - `obstaclePlanning.py`, generating a cubic fit-point spline between obstacle avoidable nodes.
    - `obstacleAvoidance.py`, testing obstacle avoidance in a straight line.
    - `Parking.py`, integrating LiDAR and camera data to parallel park effectively.
2. Develop main file `ObstacleChallenge.py`
3. Run integration tests and tune `ObstacleChallenge.py`.

### Documentation - Ryan
1. Update design journal and document engineering process.
2. Justify design and show compatibility tests.
3. Full API reference for `obstacleDetection`, `obstaclePlanning`, `obstacleAvoidance` and `parking` modules.
4. Live deployment of documentation on GitHub Pages.
## 2026-08-19
### Optimize Logic for Real-Time Speed - Michael, Elvis
1. Observe real-life behavior of the robot and identify potential improvements.
2. Refactor logical elements for maximal real-world speed, such as optimizing the path planning algorithm and reducing center of mass for better turning.
3. Comprehensively profile code and identify runtime bottlenecks.

## 2026-09-05
### Optimize Code for Runtime - Michael, Elvis
1. Optimize code to reduce runtime, such as utilizing more efficient data structures and algorithms, and leveraging hardware acceleration where possible.
2. Run comprehensive tests to ensure that optimizations do not introduce bugs or regressions.
