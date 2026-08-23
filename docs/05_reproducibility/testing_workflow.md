# Testing Workflow

Because trivial unit tests cannot replicate real-world traction, dynamic lighting, or sensor noise, our testing workflow treats track time as the SSOT (Single Source of Truth). The track is the only environment that accurately represents the real-world conditions that the robot will face during competition. While we have a comprehensive unit and integration test suite, no change is considered valid until it has been validated on the track. This ensures that our robot performs reliably under the conditions it will encounter during competition.

## Hardware Testing

Our hardware is validated directly on the robot. Running the robot on the track allows us to test the mechanical and electrical systems in a real-world environment. We perform a series of tests to ensure that all components are functioning correctly and that the robot can navigate the track as expected before committing to any changes. This includes testing the motors, sensors, and other hardware components to ensure they are working as intended.

The fast iteration cycle of 3D printing allows us to quickly prototype and test new parts. We can print a new part, install it on the robot, and test it on the track within a short period of time. This rapid prototyping process enables us to make improvements and adjustments to the hardware design based on real-world testing results. Since the hardware design is not under version control, we always make sure to keep past versions of the hardware in case we need to revert to a previous design. This allows us to change back to a previous design if a new design does not perform as expected or introduces new issues, without high opportunity cost.

Electronics are first tested in a SPICE simulation environment to validate the circuit design before being implemented on the robot. This allows us to catch any issues with the circuit design before they are implemented in hardware, which can save time and resources. Once the circuit design is validated in simulation, we implement it on the robot and test it on the track to ensure that it functions as expected in a real-world environment.

We use electronics from reputable manufacturers to ensure that the components are reliable and perform as expected. This reduces the risk of component failure during testing and competition, which can be costly and time-consuming to fix. We also perform a series of tests on the electronics to ensure that they are functioning correctly and that they can withstand the conditions of the track.

## Software Testing

Our software testing is largely automated by our CI/CD pipeline. Since some integration/system tests are impossible without a real robot and track, we focus on unit tests and integration tests that can be run in a simulated environment. This allows us to catch issues early in the development process and ensure that our code is functioning correctly before it is deployed to the robot.

All pull requests and commits to the main branch are automatically tested by the CI/CD pipeline. This ensures that any changes to the codebase are thoroughly tested and validated before they are merged into the main branch. The automated testing process helps us maintain a high level of code quality and reduces the risk of introducing bugs or issues into the system.

We also ensure all our tests are reproducible and deterministic. This means that the tests should produce the same results every time they are run, regardless of the environment or conditions. This is important for ensuring that our tests are reliable and that any issues can be consistently reproduced and addressed.

In addition to automated testing, we also perform manual testing on the robot to validate the software in a real-world environment. This includes running the robot on the track and observing its behavior to ensure that it is functioning as expected. Any issues or unexpected behavior are documented and addressed through further testing and development. If the robot fails to complete a run, we analyze the logs and video footage to identify the root cause of the failure. This information is used to make improvements to the software and hardware design, which are then tested again on the track.

Our CI/CD pipeline also includes automated documentation generation and deployment, which ensures that our public API documentation is always up-to-date with the latest code changes. This allows us to maintain accurate and comprehensive documentation for our system, which is important for both internal development and external collaboration.

## Production Fallback Plan

We always have a fallback plan in case of hardware or software failure during testing or competition. This includes having spare parts and components on hand, as well as a backup version of the software that can be deployed to the robot if necessary. We also maintain a detailed log of all changes made to the hardware and software, which allows us to quickly identify and address any issues that arise:

- All software changes are tracked in a version control system (Git) with detailed commit messages and pull request descriptions.
- All packages are uploaded to PyPI, which allows us to easily install a precompiled wheel of the software on the robot in case of a failure. This allows us to quickly revert to a known working version of the software if necessary,
perform disaster recovery during competition, and maintain a stable and reliable system throughout the development process.
- All electronics and mechanical components are labeled and organized, which allows us to quickly identify and replace any faulty components during testing or competition. Catastrophic electronic failures cannot be mitigated during a competition, so we always have a fully assembled electronics backup ready to swap in if a failure occurs. This allows us to quickly recover from any hardware failures even when under strict time constraints.
- We maintain a strict policy of at least 2 spares of each critical component, which allows us to quickly replace any faulty components during testing or competition. This ensures that the robot can continue to operate effectively even in the event of a hardware failure.
