# Constraints and Trade-offs

When engineering a robust and reliable system, there are always constraints and trade-offs to consider. These can include cost, weight, complexity, performance, and reliability. In this document, we will discuss the key constraints and trade-offs that influenced our design decisions for the 2026 WRO Future Engineer category.

## Constraints

Constraints are limitations or requirements that must be satisfied in order for the system to function as intended. These constraints can be imposed by competition rules, physical limitations, or performance requirements.

We can organize our constraints into a hierarchy, beginning with the most fundamental ("Obvious") constraints at the highest level, and moving down to more specific ("Derived") constraints at the lower levels.
To help us process and design around the constraints, we can use a "Constraint Tree" to visualize the relationships between the constraints and how they influence our design decisions.

### Constraint Tree

1. **Compliance with WRO rules and regulations**.
    1. The robot must remain within the competition size, mass, power, and mechanical limits.
        1. The chassis, drivetrain, and sensor mounts must fit within the permitted envelope.
        2. The battery and power system must remain within allowed limits.
        3. The robot must remain stable and not pose a hazard to itself or other teams.
    2. The robot must be our own work and not violate any intellectual property rights.
        1. All components must be designed and built by our team, or be commercially available and legally usable.
        2. The robot must not use any software or algorithms that are not our own work, unless they are under an OSI-approved license.
        3. The robot must avoid any design or implementation that would be considered cheating or unfair to other teams.
    3. The robot must follow timing, startup, reset, and stop procedures required by the competition.
        1. Start-up must be repeatable and not rely on undocumented manual steps.
        2. The robot must safely stop when a run ends or a fault is detected.
        3. Competition resets must restore the robot to a known-good state.

2. **Maximize score within the competition rules**.
    1. Complete the challenge objectives as reliably as possible.
        1. The robot must stay on task during wall following and path progression.
        2. The robot must identify and avoid obstacles without losing time or control.
        3. The robot must complete each lap and finish in the expected stop zone.
    2. Minimize time lost to recovery, hesitation, and detours.
        1. The control loop must respond quickly to the latest sensor data.
        2. The robot must avoid oscillations or unnecessary steering corrections.
        3. The robot must reduce the penalty cost of false detections or noisy sensor readings.
    3. Optimize the value of each decision to improve the score per unit time.
        1. High-value actions should have priority over low-value maneuvers.
        2. The system should favor stable task completion over risky aggressive moves.
        3. The robot must be able to exploit the scoring structure without violating rule constraints.

3. **Keep the design simple, reliable, and robust**.
    1. Reduce unnecessary complexity in hardware and software.
        1. Each subsystem should have a clear, single purpose.
        2. Interfaces between modules should be clean and well-defined.
        3. The system should avoid over-engineered features that do not increase score.
    2. Reduce failure modes and recovery burden.
        1. The drivetrain, sensor package, and control software should be tolerant of small calibration shifts.
        2. The robot should degrade gracefully if a sensor temporarily misreads a target.
        3. The system must be easy to debug during a competition setup or test session.
    3. Make the platform maintainable after repeated testing.
        1. Electrical connections should be accessible and labeled.
        2. Camera, serial, and control logic should be modular, so configuration changes stay localized.
        3. Adjustments to thresholds, gains, and tuning values should be easy to validate.

4. **Maximize speed while preserving reliable course completion**.
    1. Increase throughput of sensing and decision-making.
        1. The camera pipeline should keep up with the required frame rate.
        2. The vision and control logic should process new data without blocking each other.
        3. The robot should avoid stale-frame behavior by always acting on the latest information.
    2. Improve the responsiveness of the drive system.
        1. Steering and propulsion must change quickly enough to maintain course accuracy.
        2. The serial command system must not become a bottleneck during fast runs.
        3. The drive loop should minimize latency while remaining stable under load.
    3. Match speed to available energy and mechanical capability.
        1. The drivetrain must provide enough torque and traction for the chosen acceleration profile.
        2. Motor and battery selection should support the speed goals without overheating or sagging.
        3. The robot must still recover from minor disturbances without hitting obstacles or crashing into a wall.

### Higher-Order Constraint Summary

At the system level, the top-level constraints are not independent. The design must first satisfy the rule envelope (`1.x`), then the performance envelope (`2.x`), then the reliability envelope (`3.x`), and finally the speed envelope (`4.x`). In practice, all four are evaluated together, but the order matters because a design that violates rule constraints or fails reliability cannot be considered a viable solution even if it scores well or runs quickly.

## Trade-offs

Oftentimes, when engineering a system, we must make trade-offs between competing constraints. For example, increasing speed may reduce reliability, or adding more sensors may increase complexity and weight. Before we discuss the specific trade-offs we made in our design, it is important to understand the general principles of trade-offs in engineering.

### Trade-off Principles

In our engineering methodology, hard constraints (1.x–3.x) represent non-negotiable operational boundaries, while trade-offs represent bounded optimizations (e.g., speed vs. controller stability). Our goal is to maximize performance within the parameter space defined by our hard constraints. (It's important to define constraints first, because they define the solution space. Trade-offs don't matter when the judge sees your robot and says "That's illegal"!)

A trade-off is a decision to sacrifice one aspect of the system in order to improve another. For example, we may choose to reduce the weight of the robot in order to increase its speed, or we may choose to add more sensors in order to improve its reliability. Trade-offs are often necessary because no single design can optimize all aspects of a system simultaneously.

#### How we make trade-offs

We ask a series of questions to evaluate the trade-offs:

1. **Does the trade-off satisfy the solution space defined by the constraints?** If not, the trade-off is invalid and must be rejected.
2. **What aspects of the system are improved by the trade-off?** We evaluate the benefits of the trade-off, weighing more heavily on critical aspects of the system `(1.x–2.x)` than on less critical aspects `(3.x-4.x)`.
3. **What aspects of the system are sacrificed by the trade-off?** We evaluate the costs of the trade-off, weighing more heavily on critical aspects of the system `(1.x–2.x)` than on less critical aspects `(3.x-4.x)`.
4. **What is the opportunity cost of the trade-off?** We evaluate what other trade-offs could have been made instead, and whether the opportunity cost of implementing this trade-off is worthwhile in light of other potential trade-offs.
5. **Is the trade-off reversible?** We evaluate whether the trade-off can be reversed or modified later if it proves to be a poor decision. If the trade-off is irreversible, we must be more cautious in our evaluation.
  Software trade-offs are often reversible, which provides much more room for experimentation and tuning. Hardware trade-offs are often irreversible, which requires more careful consideration before making a decision.

After evaluating all these factors, we don't implement a hyper-optimized solution right away. Instead, we implement a "quick and dirty" solution that meets the basic requirements, but allows us to test the system and gather data, giving us space to re-evaluate the trade-off we made before committing to a final design. This iterative approach allows us to make informed decisions and avoid costly mistakes.

### Key Trade-offs in Our Design

Because early choices dictate downstream options (particularly across iterative cycles), we model our major design decisions as a Directed Acyclic Graph (DAG). Primary hardware choices (like steering geometry) form the root nodes, branching down into dependent software and tuning trade-offs.

[ insert a cool flowchart here ]
