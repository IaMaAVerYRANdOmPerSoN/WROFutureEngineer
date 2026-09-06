"""Tune HSV colour thresholds against the live camera feed.

This script opens the Raspberry Pi camera through :class:`AsyncCamera`,
shows the live frame, and displays the binary mask produced by the current
HSV threshold values.
"""

from collections.abc import Callable

import asyncio
from dataclasses import dataclass

import cv2
import numpy as np

from piclient.core.interface import AsyncCamera
from piclient.core.lib import GLOBAL_CONFIG


WINDOW_NAME = "HSV Tuner"

CHANNEL_LIMITS = {
    "H": 179,
    "S": 255,
    "V": 255,
}


@dataclass
class ThresholdState:
    """Mutable HSV threshold endpoints mirrored by the six trackbars.

    ``h_*`` values use OpenCV's 0-179 hue range; saturation and value fields
    use the 0-255 ranges.
    """

    h_low: int = 0
    h_high: int = CHANNEL_LIMITS["H"]
    s_low: int = 0
    s_high: int = CHANNEL_LIMITS["S"]
    v_low: int = 0
    v_high: int = CHANNEL_LIMITS["V"]


def _create_trackbars(state: ThresholdState) -> None:
    """Create the six HSV endpoint trackbars used by the tuner."""
    syncing = {"active": False}

    def _sync_channel(channel: str) -> None:
        if syncing["active"]:
            return

        syncing["active"] = True
        try:
            low_name = f"{channel} Low"
            high_name = f"{channel} High"
            low_value = cv2.getTrackbarPos(low_name, WINDOW_NAME)
            high_value = cv2.getTrackbarPos(high_name, WINDOW_NAME)

            if low_value > high_value:
                high_value = low_value
                cv2.setTrackbarPos(high_name, WINDOW_NAME, high_value)
                high_value = cv2.getTrackbarPos(high_name, WINDOW_NAME)

            setattr(state, f"{channel.lower()}_low", low_value)
            setattr(state, f"{channel.lower()}_high", high_value)
        finally:
            syncing["active"] = False

    def _make_callback(channel: str) -> Callable[[int], None]:
        return lambda _value: _sync_channel(channel)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    cv2.createTrackbar("H Low", WINDOW_NAME, state.h_low,
                       CHANNEL_LIMITS["H"], _make_callback("H"))
    cv2.createTrackbar("H High", WINDOW_NAME, state.h_high,
                       CHANNEL_LIMITS["H"], _make_callback("H"))
    cv2.createTrackbar("S Low", WINDOW_NAME, state.s_low,
                       CHANNEL_LIMITS["S"], _make_callback("S"))
    cv2.createTrackbar("S High", WINDOW_NAME, state.s_high,
                       CHANNEL_LIMITS["S"], _make_callback("S"))
    cv2.createTrackbar("V Low", WINDOW_NAME, state.v_low,
                       CHANNEL_LIMITS["V"], _make_callback("V"))
    cv2.createTrackbar("V High", WINDOW_NAME, state.v_high,
                       CHANNEL_LIMITS["V"], _make_callback("V"))


def _read_thresholds() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Read the current threshold values from the trackbars."""
    lower = (
        cv2.getTrackbarPos("H Low", WINDOW_NAME),
        cv2.getTrackbarPos("S Low", WINDOW_NAME),
        cv2.getTrackbarPos("V Low", WINDOW_NAME),
    )
    upper = (
        cv2.getTrackbarPos("H High", WINDOW_NAME),
        cv2.getTrackbarPos("S High", WINDOW_NAME),
        cv2.getTrackbarPos("V High", WINDOW_NAME),
    )
    return lower, upper


def _overlay_status(frame: np.ndarray[tuple[int, int, int], np.dtype[np.uint8]], lower: tuple[int, int, int], upper: tuple[int, int, int]) -> None:
    """Draw the current threshold values and exit hint onto the source frame."""
    cv2.putText(
        frame,
        "Q/Esc: quit, S: Log thresholds",
        (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"Lower: {lower} Upper: {upper}",
        (10, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def _compose_display(frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Combine the mask on the left and source frame on the right."""
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    return np.concatenate((mask_bgr, frame), axis=1)


async def run_color_threshold_tuner() -> None:
    """Run the live-camera HSV tuner until ``q`` or Escape is pressed.

    Frames are converted from BGR to HSV, thresholded with the trackbar values,
    and displayed beside the source frame. Pressing ``s`` prints the current
    lower and upper bounds. Requires camera hardware and an OpenCV GUI session.
    """
    camera_config = GLOBAL_CONFIG().CameraConfig
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, camera_config.OUTPUT_WIDTH *
                     2, camera_config.OUTPUT_HEIGHT)

    state = ThresholdState()
    _create_trackbars(state)

    try:
        async with AsyncCamera() as camera:
            while True:
                frame: np.ndarray[tuple[int, int, int], np.dtype[np.uint8]] | None = await camera.get_frame_async()
                if frame is None:
                    continue

                lower, upper = _read_thresholds()
                hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv_frame, lower, upper)

                _overlay_status(frame, lower, upper)
                display = _compose_display(frame, mask)

                cv2.imshow(WINDOW_NAME, display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("s"):
                    print(f"Lower: {lower}, Upper: {upper}")
                if key in (ord("q"), 27):
                    break
    finally:
        cv2.destroyAllWindows()


def main() -> None:
    """Start the asyncio event loop for the HSV tuner and GUI windows."""
    asyncio.run(run_color_threshold_tuner())


if __name__ == "__main__":
    main()
