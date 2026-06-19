"""Raw camera feed tool.

Displays the unprocessed camera feed before and after perspective
transformation, with no overlays.
"""

from utils import cv2
import numpy as np
from utils.tools.base_tool import BaseTool
from src.piclient.lib.config import Config


class RawTool(BaseTool):
    """Tool for viewing the raw camera feed."""
    def __init__(self):
        super().__init__(name="raw",
                         description="View raw camera feed before and after perspective transformation, no overlays")

    def _draw_base(self, frame, *args, **kwargs):
        """Identity pass-through for the raw frame.

        :param frame: Frame to display.
        :returns: The same frame, unmodified.
        """
        return frame

    def _draw(self, data, *args, **kwargs):
        """Draw the perspective-warped raw frame.

        :param data: Vision pipeline output tuple (unused for raw view).
        """
        self._ensure_windows("Raw Feed")
        frame = cv2.warpPerspective(
            self.frame, Config.VisionConfig.PERSPECTIVE_TRANSFORM, (self.frame.shape[1], self.frame.shape[0]))
        # The contours are already in perspective-transformed coordinates, so we can draw them directly on the warped frame
        frame = self._draw_base(frame, *args, **kwargs)
        cv2.imshow("Raw Feed", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        """Draw the raw (unwarped) frame.

        :param data: Vision pipeline output tuple (unused for raw view).
        """
        self._ensure_windows("Raw Feed - No Perspective")
        frame = self.frame.copy()
        # Same drawing logic, just different data and window title
        frame = self._draw_base(frame, *args, **kwargs)
        cv2.imshow("Raw Feed - No Perspective", frame)


async def run_raw_tool():
    """Entry point for the raw camera feed tool."""
    tool = RawTool()
    await tool.run()
