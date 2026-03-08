# WRO 2026 Future Engineers – TEAM APOSTLA

## Project Overview
This repository contains the complete documentation, code, design files, and test records for our **WRO 2026 Future Engineers** self-driving car project.

This repo is organized to show:
- how our robot is mechanically designed
- how power and sensors are arranged
- how the software is structured
- how engineering decisions were made
- how another team could reproduce the robot

---

## Team Information
- **Team Members:** Elvis Wang, Michael Xie, Ryan Rao
- **Coach / Mentor:** Huifei Rao

### *add more info about team and stuff*

---

## Robot Summary
Briefly describe your robot in 3–6 sentences.

Example:
> Our robot is a self-driving vehicle designed for the WRO 2026 Future Engineers challenge. It uses [camera / LiDAR / ultrasonic / IMU / other sensors] to detect the environment, follow the track, and react to obstacles. The robot is built with [main controller], [drive system], and [steering mechanism]. Our design focuses on [stability / reliability / fast turning / accurate detection / modularity].

### Main Features
- [Feature 1]
- [Feature 2]
- [Feature 3]
- [Feature 4]


---

## Repository Structure

### Main Files
- `README.md` – main project overview and navigation
- `LICENSE` – repository license
- `.gitignore` – ignored local/generated files
- `requirements.txt` – Python dependencies
- `CHANGELOG.md` – version history

### Documentation
- `docs/01_mechanical/` – mobility and mechanical design
- `docs/02_power_sensors/` – power system and sensor architecture
- `docs/03_software/` – software design and obstacle strategy
- `docs/04_systems_engineering/` – engineering decisions, trade-offs, and risks
- `docs/05_reproducibility/` – build, setup, assembly, and testing workflow

### Other Project Assets
- `cad/` – CAD models and mechanical design files
- `wiring/` – wiring diagrams and connector information
- `src/` – source code
- `tests/` – testing scripts, procedures, and logs
- `data/` – calibration data and experiment results
- `media/` – photos, screenshots, and videos
- `submissions/` – final competition submission materials

---

# 1. Mechanical Design
This section explains the physical design of the robot, including chassis layout, steering, drivetrain, torque/speed reasoning, and mechanical improvements over time.

### Files
- [`docs/01_mechanical/chassis_design.md`](docs/01_mechanical/chassis_design.md)
- [`docs/01_mechanical/steering_drive.md`](docs/01_mechanical/steering_drive.md)
- [`docs/01_mechanical/torque_speed_reasoning.md`](docs/01_mechanical/torque_speed_reasoning.md)
- [`docs/01_mechanical/mechanical_iterations.md`](docs/01_mechanical/mechanical_iterations.md)

### Summary
Write a short summary here:
- chassis type:
- steering type:
- drivetrain type:
- major mechanical priorities:
- key lessons learned:

---

# 2. Power and Sensor Architecture
This section explains how the robot is powered, what sensors are used, where they are placed, and how they are calibrated.

### Files
- [`docs/02_power_sensors/power_architecture.md`](docs/02_power_sensors/power_architecture.md)
- [`docs/02_power_sensors/sensor_selection.md`](docs/02_power_sensors/sensor_selection.md)
- [`docs/02_power_sensors/sensor_placement.md`](docs/02_power_sensors/sensor_placement.md)
- [`docs/02_power_sensors/calibration.md`](docs/02_power_sensors/calibration.md)
- [`docs/02_power_sensors/wiring.md`](docs/02_power_sensors/wiring.md)

### Summary
Write a short summary here:
- battery:
- voltage regulation:
- main sensors:
- sensor placement strategy:
- calibration approach:

---

# 3. Software Architecture and Strategy
This section explains how the code is structured and how the robot performs lane following, obstacle handling, and control.

### Files
- [`docs/03_software/software_architecture.md`](docs/03_software/software_architecture.md)
- [`docs/03_software/state_machine.md`](docs/03_software/state_machine.md)
- [`docs/03_software/lane_following.md`](docs/03_software/lane_following.md)
- [`docs/03_software/obstacle_strategy.md`](docs/03_software/obstacle_strategy.md)
- [`docs/03_software/algorithms.md`](docs/03_software/algorithms.md)
- [`docs/03_software/edge_cases.md`](docs/03_software/edge_cases.md)
- [`docs/03_software/tuning_validation.md`](docs/03_software/tuning_validation.md)

### Summary
Write a short summary here:
- main programming language:
- code structure:
- lane following method:
- obstacle handling method:
- important algorithms:
- tuning process:

---

# 4. Systems Engineering and Design Decisions
This section explains how the robot was developed as an integrated system and how trade-offs were evaluated.

### Files
- [`docs/04_systems_engineering/subsystem_interactions.md`](docs/04_systems_engineering/subsystem_interactions.md)
- [`docs/04_systems_engineering/engineering_decisions.md`](docs/04_systems_engineering/engineering_decisions.md)
- [`docs/04_systems_engineering/constraints_tradeoffs.md`](docs/04_systems_engineering/constraints_tradeoffs.md)
- [`docs/04_systems_engineering/risk_analysis.md`](docs/04_systems_engineering/risk_analysis.md)
- [`docs/04_systems_engineering/iteration_cycles.md`](docs/04_systems_engineering/iteration_cycles.md)

### Summary
Write a short summary here:
- biggest engineering constraints:
- main trade-offs:
- most important decisions:
- major risks:
- how the robot improved through iteration:

---

# 5. Reproducibility
This section explains how another team could rebuild, set up, and test the robot.

### Files
- [`docs/05_reproducibility/build_guide.md`](docs/05_reproducibility/build_guide.md)
- [`docs/05_reproducibility/bill_of_materials.md`](docs/05_reproducibility/bill_of_materials.md)
- [`docs/05_reproducibility/assembly_steps.md`](docs/05_reproducibility/assembly_steps.md)
- [`docs/05_reproducibility/setup_guide.md`](docs/05_reproducibility/setup_guide.md)
- [`docs/05_reproducibility/testing_workflow.md`](docs/05_reproducibility/testing_workflow.md)
- [`docs/05_reproducibility/release_notes.md`](docs/05_reproducibility/release_notes.md)

### Summary
Write a short summary here:
- how to build the robot:
- how to install software:
- how to calibrate:
- how to test:
- what files are needed to reproduce the system:

---

## Hardware Summary
Fill in this quick-reference hardware list.

| Component | Model / Part | Purpose |
|----------|---------------|---------|
| Main controller |  |  |
| Secondary controller |  |  |
| Drive motor |  |  |
| Steering servo |  |  |
| Motor driver / ESC |  |  |
| Camera |  |  |
| LiDAR / distance sensor |  |  |
| IMU |  |  |
| Battery |  |  |
| Voltage regulator / BEC |  |  |

---

## Software Summary
Fill in this quick-reference software list.

| Item | Description |
|------|-------------|
| Main language |  |
| Main controller software |  |
| Secondary controller software |  |
| Main control loop |  |
| Perception method |  |
| Planning method |  |
| Steering control method |  |
| Speed control method |  |

---

## Build and Setup Quick Start
Give a short version here, and keep the detailed steps in `docs/05_reproducibility/`.

1. Build the chassis
2. Mount electronics
3. Connect wiring
4. Install software dependencies
5. Upload or run code
6. Calibrate sensors
7. Run tests

Detailed instructions:
- [`docs/05_reproducibility/build_guide.md`](docs/05_reproducibility/build_guide.md)
- [`docs/05_reproducibility/setup_guide.md`](docs/05_reproducibility/setup_guide.md)

---

## Testing and Validation
Summarize how the robot was tested.

Example points:
- bench tests for hardware
- sensor tests
- steering tests
- lane following tests
- obstacle avoidance tests
- full track tests

Detailed records:
- `tests/`
- `data/`
- [`docs/03_software/tuning_validation.md`](docs/03_software/tuning_validation.md)
- [`docs/04_systems_engineering/iteration_cycles.md`](docs/04_systems_engineering/iteration_cycles.md)

---

## Media and Visual Documentation
Use this section to point judges to photos, diagrams, and videos.

### Photos
- overall robot:
- front view:
- top view:
- sensor placement:
- wiring overview:

### Diagrams
- chassis diagram:
- power diagram:
- wiring diagram:
- software flowchart:
- state machine diagram:

### Videos
- robot demo:
- obstacle handling demo:
- testing clips:

Suggested folders:
- `media/`
- `docs/images/`
- `docs/diagrams/`
- `docs/videos/`

---

## CAD and Wiring Files
- `cad/` – CAD files and exports
- `wiring/` – wiring diagrams and connection references

Brief notes:
- CAD software used:
- file format(s):
- wiring diagram tool used:

---

## Version History
Briefly summarize major milestones here.

See full details in:
- [`CHANGELOG.md`](CHANGELOG.md)
- [`docs/05_reproducibility/release_notes.md`](docs/05_reproducibility/release_notes.md)

Example:
- **v0.1** – initial repo structure
- **v0.2** – first rolling prototype
- **v0.3** – improved steering and sensor placement
- **v0.4** – implemented lane following and obstacle response

---

## Contribution and Documentation Rules
Use this section to keep the repo organized.

Example:
- use clear commit messages
- add photos when mechanical changes are made
- document sensor changes in `sensor_placement.md`
- document tuning changes in `tuning_validation.md`
- document major engineering decisions in `engineering_decisions.md`

---

## Final Notes
This repository is intended to document not only the final robot, but also the engineering process behind it:
- design choices
- testing evidence
- failures and improvements
- reproducibility

The goal is to make the project understandable, traceable, and reproducible.
