# Goals
> *Crossed out words mean objective completed*
## Electrical Objectives

- Make schematic for the robot, because apprently PCBs take months to ship and it ain't coming. So make the schematic for the raw wiring and then just solder it together on a perfboard or something.
- Integrate LiDAR into the electronics.

## Coding Objectives

- "When you feel like you need reliability SLAs for a three man team working on a high school robotics project, you have already lost." - Me, March 26, 2026.
- Write integration tests for all modules, and make sure to test the robot on the actual track as much as possible.
- Integrate LiDAR into the codebase once the module for it is done, and make sure to test it on the track as well.
- Integrate sphinx and write docstrings for all modules, also group it into private and public APIs. Spend uh... way too much time on frontend aesthetics and making a beautiful documentation website that no one will read.
- Make LiDAR work :hmmyes:
- ~~Refactor all modules in src_min to drop async and multiprocessing and multithreading, and instead use a single-threaded, synchronous design.~~
- ~~KISS, discard two months of work because I am a fucking idiot that overengineered everything and can't stop myself from doing it.~~

Okay here's the notes from coach :sob: (I liked the fancy stuff):

>- Architecture is over-engineered for the open challenge — async/await, multiprocessing, shared memory, pipes, and thread pools are unnecessary for a robot that just needs to follow walls and turn corners.
>- The added complexity creates more failure points and makes debugging under competition pressure much harder.
>- Since everything depends on the latest camera frame, there is no real benefit to running things concurrently.
>- Suggested simplified structure: main.py, camera.py, vision.py, comm.py, controller.py, config.py — each a plain synchronous class with no async or multiprocessing.
>- All tunable constants should be moved into a single config.py file.
>- Keep the multi-file structure but drop the async complexity — a solution every team member can read and debug under pressure beats an elegant but complicated one.
    - [see coach comments](../docs/coach_comments.md#april-11th)

## Mechanical Objectives

List of things to improve but not big enough to print a new part for:

> ~~- Add a place to screw in voltage regulator~~  
> ~~- Make camera angle more downwards~~  
> ~~- Create a Lidar holder + make space for it~~  
> ~~- Fix differential gear issue~~

> - Create a spot to put switch
