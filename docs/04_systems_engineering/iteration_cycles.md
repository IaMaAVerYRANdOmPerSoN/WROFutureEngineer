# Design Iteration

When designing a complex system, we often face trade-offs between different design choices. These trade-offs can be difficult to evaluate, as they often involve multiple factors and dependencies. To help us make informed decisions, we use an iterative design process that allows us to test and refine our designs over time.

## Practical Examples

### Differential Gear Design

Our differential gear design went through several iterations, each with its own set of trade-offs and limitations. The table below summarizes the different versions of our differential gear design, along with their design goals, limitations, and takeaways.

| Version | Design Goals | Limitations | Takeaways |
| --- | --- | --- | --- |
| 1 | Adapt a preliminary GrabCAD differential with minor modifications. | The design ignored our size constraints. The teeth did not mesh, wore quickly, and broke at increased speed. | Existing designs must be evaluated against our constraints before testing. |
| 2 | Design the differential from scratch around our size constraints. | Gear wear still caused skipping, rapid direction changes caused locking, and poor meshing generated temperatures exceeding PLA glass transition temperatures. | Material constraints and operating conditions must be considered alongside geometry. |
| 3 | Improve meshing and alignment by adding axles inside the rotating cage and securing all moving components. | The added complexity made tolerance tuning difficult. Friction increased wear, and the design couldn't overcome the surface finish limitations of FDM 3D printing. | A more robust design can introduce new friction, tolerance, and manufacturing problems. |
| 4 | Use a robust metal differential designed for RC cars. | The differential was too large for the universal axles, rubbed against the floor, and bent the rear assembly because of its weight. | Components cannot be viewed in isolation; they are constrained by and must be viewed in the context of the entire system. |
| 5 | Use a compact differential gearbox salvaged from a smaller RC car (1/24–1/28). | The gearbox was salvaged rather than purpose-built. No backups available, and the design is not easily reproducible. | The smaller, lighter, self-contained gearbox eliminated 3D-printed gears, reduced complexity, fit the design constraints, and provided a good overall trade-off. |

Despite pivoting our design in fundamentally different directions two times, we were able to converge on a final design that met our requirements and constraints. Iteration 1-3 focused on mitigating a fundamental material constraint in FDM PLA, while iteration 4-5 were architectural shifts to completely different models that better meet our requirements. We learned that testing more approaches and iterating quickly near the start of the design process is more effective than premature optimization of a single approach.

### Python Packaging

Our Python packaging design also went through several iterations, each with its own set of trade-offs and limitations. The table below summarizes the different approaches we considered for packaging our Python code, along with their design goals, limitations, and takeaways.

| Version | Design Goals | Limitations | Takeaways |
| --- | --- | --- | --- |
| 1 | No packaging, just a single src directory with module-level imports. | Isolation of concerns and DRY suffered, and the architecture becomes tightly coupled without clear interfaces and boundaries. | A single src directory is not a sustainable architecture considering the scope of our project. |
| 2 | Independently maintain a simpler `src_min` implementation with a single src directory, forgoing complex multiprocessing and asynchronous IO. | While the simple implementation is easier to maintain, it doesn't meet our performance constraints, and the additional burden of maintaining two separate implementations is significant. | A simpler, slower implementation is a trade-off we couldn't accept given our latency and throughput requirements. |
| 3 | Use multiple sub-packages within a single src directory. | The architecture is still tightly coupled, and the sub-packages are not easily reusable or distributable. | Sub-packages are a step in the right direction, but they do not provide enough isolation of concerns or reusability. |
| 4 | Adopt a namespace package architecture with multiple sub-packages, each with distribution metadata (`pyproject.toml`) and clearly defined exports. | Complex packaging requirements, requiring deep understanding of Python packaging and distribution. | Namespace packages provide a sustainable architecture with clear interfaces and independently distributable components. |

We've adopted the gold standard for Python packaging: a namespace package architecture that provides clear interfaces and independently distributable components. While this approach introduces complex packaging constraints, it is a sustainable architecture that can support the growth and evolution of our project over time. It's a solution many Python projects have adopted, and it is the recommended approach for large, complex projects that require modularity and reusability.

Our codebase is highly complex, with a multi-process producer-consumer model, asynchronous IO, and low-latency/high-throughput requirements. Our pipeline would have experienced untraceable race conditions and shared memory allocation failures if the interfaces between producers and consumers (Camera (Asynchronous) → SHM (Shared Memory) → Vision Processor (multithreaded) → State Machine/Controller → Asynchronous Hardware Interfaces and Custom Protocols → Hardware) were not clearly defined and enforced. The level of introspection and logging currently in place would not have been possible without the namespace package architecture, as the recorder and logging consumers would not have been able to interface with the tightly coupled camera → processor → control pipeline.

Even though we had to invest significant time and effort into understanding and implementing a namespace package architecture, it has paid off in the long run. We're able to distribute our codebase to potential future teams, and they can easily understand and modify the code without having to navigate a tightly coupled monolithic architecture. We invite you to install our packages and play around on your own robots! Please see our [Setup Guide](./setup_guide.md) for instructions on how to install and use our packages.