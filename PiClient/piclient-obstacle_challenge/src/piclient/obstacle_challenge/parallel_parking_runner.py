"""
Integration test runner for the parallel parking challenge. Runs the parallel parking routine in independently of other components.
"""

from loguru import logger

from piclient.core.interface import AsyncCamera, DriveCommandExecutor, Client
from piclient.core.lib import ProcessContextManager, export
from piclient.core.vision import ObstacleChallengeAsyncMultiprocessingVisionProcessor, WallsAndObstacles

from .parallel_parking import ParallelParkingStateMachine


@export
@logger.contextualize(process="MAIN")
async def run_parallel_parking() -> None:
    """Run the parallel-parking routine using live camera and vision data.

    The routine owns the camera, vision process, serial client, and parking
    state machine for one run and logs unexpected failures without re-raising
    them.

    :returns: ``None`` after parking completes or is interrupted.
    :rtype: None
    """
    process_manager = ProcessContextManager(
        camera_callback=AsyncCamera.camera_process_context_manager,
        vision_callback=ObstacleChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager,
    )

    try:
        async with Client() as client:
            drive_executor = DriveCommandExecutor(client=client)
            async with ParallelParkingStateMachine(
                drive_command_executor=drive_executor,
                round_driving_direction="CLOCKWISE"  # Arbitrary choice for testing determined by environment in real obstacle challenge
            ) as state_machine:
                with process_manager as process_context:
                    if process_context.output_stream is None:
                        raise RuntimeError("Output stream is not initialized.")

                    async for data in ObstacleChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(process_context.output_stream):
                        walls_and_obstacles: WallsAndObstacles = data[0]

                        state_machine.update(walls_and_obstacles)
                        finished = state_machine.handle_state_actions()

                        if finished:
                            break
    except KeyboardInterrupt:
        logger.error("Parallel parking runner interrupted by user.")
    except Exception:
        logger.exception(f"An error occurred during parallel parking:")

if __name__ == "__main__":
    import asyncio

    asyncio.run(run_parallel_parking())