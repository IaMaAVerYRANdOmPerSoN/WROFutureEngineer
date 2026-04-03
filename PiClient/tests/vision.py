import asyncio
import numpy as np
import cv2
from src.asyncCamera import AsyncCamera
from src.visionProcessing import VisionObject
from src.visionProcessing import AsyncVisionProcessor
from loguru import logger
import multiprocessing as mp
from multiprocessing import shared_memory
import sys

logger.remove()
logger.add("vision.log", rotation="1 MB", retention="10 days", level="INFO")
logger.add(sys.stdout, level="INFO", filter=lambda record: record["level"].no < logger.level("ERROR").no)
logger.add(sys.stderr, level="ERROR")


def _draw_detections(frame, zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists):
    color_map = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "green": (0, 200, 0),
        "red": (0, 0, 255),
        "blue": (255, 0, 0),
        "orange": (0, 165, 255),
    }

    def draw_object(obj, label, thickness=2):
        color = color_map.get(getattr(obj, "color", ""), (255, 255, 0))
        cv2.drawContours(frame, [obj.contour], -1, color, thickness)
        x, y, w, h = obj.bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
        cv2.putText(
            frame,
            label,
            (x, max(12, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    if zone:
        draw_object(zone, "zone", thickness=2)

    for idx, wall in enumerate(walls):
        draw_object(wall, f"wall{idx}")

    for idx, obstacle in enumerate(obstacles):
        draw_object(obstacle, f"obs{idx}:{obstacle.color}")

    for idx, line in enumerate(corner_lines):
        draw_object(line, f"corner{idx}")

    h, w = frame.shape[:2]
    cv2.line(frame, (w // 2, 0), (w // 2, h), (60, 60, 60), 1)

    status_lines = [
        f"WallDist L:{wall_dists['left']:.1f} R:{wall_dists['right']:.1f}",
        "ObstacleDist " + (", ".join(f"{d:.1f}" for d in obstacle_dists) if obstacle_dists else "none"),
    ]
    for i, text in enumerate(status_lines):
        cv2.putText(
            frame,
            text,
            (8, 18 + i * 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return frame

def camera(shm, sender):
    async def _run():
        async with AsyncCamera() as camera:
            await camera.stream(shm, sender)

    asyncio.run(_run())

def vision(shm, sender, receiver):
    async def _run():
        async with AsyncVisionProcessor() as vision:
            await vision.comprehensive_analysis(shm, sender, receiver)
    
    asyncio.run(_run())

async def run_tests():
    logger.info("Starting Vision Unittest...")
    shm_name = "frameBuffer"
    shm_size = 384*512*3 + 128  # Frame + 128 bytes margin

    try:
        shm = shared_memory.SharedMemory(name=shm_name, create=True, size=shm_size)
    except FileExistsError:
        # Clean up any stale shared memory segment from a previous run and retry
        try:
            existing_shm = shared_memory.SharedMemory(name=shm_name, create=False)
            existing_shm.close()
            existing_shm.unlink()
        except FileNotFoundError:
            # The shared memory segment disappeared between create and cleanup attempts
            pass
        shm = shared_memory.SharedMemory(name=shm_name, create=True, size=shm_size)

    frameReceiver, frameSender = mp.Pipe(duplex=False)
    dataReceiver, dataSender = mp.Pipe(duplex=False)

    camera_stream = mp.Process(group=None, target=camera, args=(shm_name, frameSender,), daemon=False)
    camera_stream.start()

    data_stream = mp.Process(group=None, target=vision, args=(shm_name, dataSender, frameReceiver,), daemon=False)
    data_stream.start()
        
    try:
        async for zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists in AsyncVisionProcessor.data_yielder(dataReceiver):
            try:
                assert isinstance(zone, VisionObject) or zone is None, f"Zone is not a VisionObject or None: {type(zone)}"
                assert isinstance(walls, tuple) and all(isinstance(wall, VisionObject) for wall in walls), f"Walls is not a tuple of VisionObjects: {type(walls)} with elements {[type(wall) for wall in walls]}"
                assert isinstance(obstacles, tuple) and all(isinstance(obstacle, VisionObject) for obstacle in obstacles), f"Obstacles is not a tuple of VisionObjects: {type(obstacles)} with elements {[type(obstacle) for obstacle in obstacles]}"
                assert isinstance(corner_lines, tuple) and all(isinstance(line, VisionObject) for line in corner_lines), f"Corner lines is not a tuple of VisionObjects: {type(corner_lines)} with elements {[type(line) for line in corner_lines]}"
                assert isinstance(wall_dists, dict) and all(isinstance(dist, (int, float)) for dist in wall_dists.values()), f"Wall distances is not a dict of numbers: {type(wall_dists)} with values {[type(dist) for dist in wall_dists.values()]}"
                assert isinstance(obstacle_dists, list) and all(isinstance(dist, (int, float)) for dist in obstacle_dists), f"Obstacle distances is not a list of numbers: {type(obstacle_dists)} with values {[type(dist) for dist in obstacle_dists]}"
            except AssertionError as e:
                logger.error(f"Data validation error: {e}")
                continue  # Skip this frame but keep processing future frames

            logger.info(
                f"Zone {zone}\n" \
                f"Walls: {walls} \n" \
                f"Obstacles: {obstacles} \n" \
                f"Corner Lines: {corner_lines} \n" \
                f"Wall distances {wall_dists} \n" \
                f"Obstacle Distances {obstacle_dists} \n")

            frame = np.ndarray((384, 512, 3), dtype=np.uint8, buffer=shm.buf[:384 * 512 * 3]).copy()
            display = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR)
            display = _draw_detections(display, zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists)
            cv2.imshow("Vision Debug", display)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

    finally:
        camera_stream.terminate()
        data_stream.terminate()
        camera_stream.join()
        data_stream.join()
        shm.close()
        shm.unlink()
        cv2.destroyAllWindows()