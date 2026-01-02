import asyncio
import sys
from loguru import logger
from commProtocol import Client
from visionProcessing import AsyncVisionProcessor
from asyncCamera import AsyncCamera
from controller import PD
import multiprocessing as mp

logger.remove()
fmt = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
    "<cyan>{line:03}: {function: <18}</cyan> │ "
    "<level>{level: <8}</level> │ "
    "<level>{message}</level>")
logger.add(sys.stderr, level="WARNING", format=fmt)
logger.add("log.txt", level="WARNING", enqueue=True, rotation="5 MB", retention="10 days", format=fmt)
logger.add("verbose.txt", level="DEBUG", enqueue=True, rotation="1 MB", retention="3 days", format=fmt, backtrace=True, diagnose=True)

async def main():
    async with Client() as client, AsyncVisionProcessor() as vision, AsyncCamera() as camera:
        controller = PD(1, 0.2)

        # Starting code here
        state = "Follow wall"
        look_ahead_task = None

        reciver, sender = mp.Pipe(duplex = False)

        camera_process = mp.Process(target = camera.stream, args=(sender,))
        camera_process.start()

        async for frame in camera.frame_yeilder(reciver):
            zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_dists = await vision.comprehensive_analysis(frame)

            # Some check for end condition here
            if zone:
                if any(wall_x_diffs.values() < 30):
                    state = "Follow wall"

                elif obstacles:
                    state = "Avoid obstacles"

                elif corner_lines:
                    state = "Turn"

                else:
                    state = "Follow wall"

            match state:
                case "Avoid obstacles":
                    largest_obstacle = obstacles[0]
                    distance, *_ = obstacle_dists[0]

                    if largest_obstacle.color == "red": # Pass to the right
                        if largest_obstacle.x_centroid >= 80: # Both obstacle and wall to the right
                            midpoint = (distance + wall_x_diffs["right"]) / 2
                        else: # Obstacle to the left, right wall (passing to the right)
                            midpoint = (wall_x_diffs["right"] - distance) / 2

                    if look_ahead_task:
                        look_ahead_task.cancel()
                    
                    look_ahead_task = asyncio.create_task(client.fast_arc_to_target(midpoint, largest_obstacle.bottom_y)) # Need more rigorous distance estimation

                case "Turn":
                    # Create a series of commands to turn to the next straight section.
                    pass

                case "Follow wall":
                    logger.debug(f"State: Follow Wall")

                    detected_walls = {k: v for k, v in wall_x_diffs.items() if v != float("inf")}
                    closest_wall = min(detected_walls.keys(), key = lambda k: detected_walls.get(k))

                    servo_angle = controller.tick(30, detected_walls[closest_wall]) if closest_wall == "left" else -controller.tick(30, detected_walls[closest_wall]) # negative steering is towards the left

                    asyncio.create_task(client.set_servo_angle(servo_angle))
                    asyncio.create_task(client.drive_motors(6, 0.1)) # Defaults to overwriting, will simply overwrite next iteration
                    

if __name__ == "__main__":
    try:
        asyncio.run(main())
        exitcode = 0
    except KeyboardInterrupt:
        logger.error("Process Interupted by User")
        exitcode = 0
    except Exception:
        logger.exception("A FATAL EXECPTION HAS OCCURED")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        if 'camera_process' in locals():
            locals["camera_process"].terminate()
            locals["camera_process"].join()
        logger.info("Cleanup complete.")
        logger.remove()
        sys.exit(exitcode)
