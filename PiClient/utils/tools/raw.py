from utils import cv2
import numpy as np
from utils.tools.base_tool import BaseTool
from src.modules.config import Config


class RawTool(BaseTool):
    def __init__(self):
        super().__init__(name="raw",
                         description="View raw camera feed before and after perspective transformation, no overlays")

    def _draw_base(self, frame, *args, **kwargs):
        return frame

    def _draw(self, data, *args, **kwargs):
        self._ensure_windows("Raw Feed")
        frame = cv2.warpPerspective(
            self.frame, Config.VisionConfig.PERSPECTIVE_TRANSFORM, (self.frame.shape[1], self.frame.shape[0]))
        # The contours are already in perspective-transformed coordinates, so we can draw them directly on the warped frame
        frame = self._draw_base(frame, *args, **kwargs)
        cv2.imshow("Raw Feed", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        self._ensure_windows("Raw Feed - No Perspective")
        frame = self.frame.copy()
        # Same drawing logic, just different data and window title
        frame = self._draw_base(frame, *args, **kwargs)
        cv2.imshow("Raw Feed - No Perspective", frame)


async def run_raw_tool():
    tool = RawTool()
    await tool.run()
