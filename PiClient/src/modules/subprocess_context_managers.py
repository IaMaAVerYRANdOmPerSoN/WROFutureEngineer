# TODO: Should probably provide these as static methods on the respective classes, but uh this work for now and i'm lazy okay :3
import asyncio
from src.modules.async_camera import AsyncCamera
from src.modules.vision_processing import AsyncMultiprocessingVisionProcessor

def camera_process_context_manager(shm, sender):
    async def _run():
        async with AsyncCamera() as camera:
            await camera.stream(shm, sender)

    asyncio.run(_run())


def vision_process_context_manager(shm, frameReceiver, data_sender):
    async def _run():
        async with AsyncMultiprocessingVisionProcessor() as vision:
            await vision.comprehensive_analysis(shm, frameReceiver, data_sender)

    asyncio.run(_run())