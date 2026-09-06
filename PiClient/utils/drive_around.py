"""Drive the robot manually from an OpenCV camera preview.

The script requires Raspberry Pi camera hardware and an Arduino serial
connection. Key presses produce short normalized-speed drive commands.
"""
import asyncio
import cv2
from piclient.core.interface import AsyncCamera, Client, DriveCommandExecutor
from piclient.core.lib import GLOBAL_CONFIG


WINDOW_NAME = "Drive Around"
DRIVE_COMMAND_DURATION = 0.03
STEERING_CENTER = 90.0
STEERING_OFFSET = 30.0


def move(longitudinal: float, theta: float, key: int) -> tuple[float, float, bool]:
    """Update the robot's movement from a cv2 key code.

    The OpenCV window does not provide key-up events, so state persists between
    calls. ``w``/``s`` select ``-0.35``/``0.35`` longitudinal speed, ``x`` or
    space stops, ``a``/``d`` select steering angles 120/60 degrees, ``z`` or
    space centers steering, and ``q``/Escape requests quit.

    :returns: Updated ``(longitudinal_speed, steering_angle, should_quit)``.
    """
    if key in (ord("q"), 27):
        return longitudinal, theta, True

    if key == ord("w"):
        longitudinal = -0.35
    elif key == ord("s"):
        longitudinal = 0.35
    elif key == ord("x") or key == 32:
        longitudinal = 0.0

    if key == ord("a"):
        theta = STEERING_CENTER + STEERING_OFFSET
    elif key == ord("d"):
        theta = STEERING_CENTER - STEERING_OFFSET
    elif key == ord("z") or key == 32:
        theta = STEERING_CENTER

    return longitudinal, theta, False


async def drive_around() -> None:
    """Open camera/serial contexts and drive until the user quits.

    Camera frames are displayed with current command state. Context managers
    stop the robot and release camera, serial, executor, and GUI resources on
    normal exit or failure.
    """
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        WINDOW_NAME,
        GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH,
        GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT,
    )

    longitudinal = 0.0
    theta = STEERING_CENTER

    async with AsyncCamera() as camera:
        async with Client() as client, DriveCommandExecutor(client) as executor:
            try:
                while True:
                    frame = await camera.get_frame_async()
                    if frame is None:
                        continue

                    cv2.putText(
                        frame,
                        "W/S: forward/back | A/D: turn | X/Space: stop | Q/Esc: quit",
                        (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )
                    cv2.putText(
                        frame,
                        f"Longitudinal: {longitudinal:.2f}  Theta: {theta:.1f}",
                        (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )

                    cv2.imshow(WINDOW_NAME, frame)
                    key = cv2.waitKey(1) & 0xFF
                    longitudinal, theta, should_quit = move(
                        longitudinal, theta, key)
                    executor.submit(longitudinal, theta,
                                    DRIVE_COMMAND_DURATION)

                    if should_quit:
                        break
            finally:
                cv2.destroyWindow(WINDOW_NAME)
                executor.submit(0.0, STEERING_CENTER, DRIVE_COMMAND_DURATION)

if __name__ == "__main__":
    asyncio.run(drive_around())
