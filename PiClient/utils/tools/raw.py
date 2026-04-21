import cv2
from utils.tools.base_tool import BaseTool
from src.config import Config

class RawTool(BaseTool):
    def __init__(self):
        super().__init__(name="raw", description="View raw camera feed before and after perspective transformation, no overlays")


    def _draw_base(self, frame, *args, **kwargs):
        return frame

    def _draw(self, data, *args, **kwargs):
        frame = cv2.warpPerspective(self.frame, Config.VisionConfig.PERSPECTIVE_TRANSFORM, (self.frame.shape[1], self.frame.shape[0]))
        frame = self._draw_base(frame, *args, **kwargs) # The contours are already in perspective-transformed coordinates, so we can draw them directly on the warped frame
        cv2.imshow("Raw Feed", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        frame = self.frame.copy()
        frame = self._draw_base(frame, *args, **kwargs) # Same drawing logic, just different data and window title
        cv2.imshow("Raw Feed - No Perspective", frame)
    
async def run_raw_tool():
    tool = RawTool()
    await tool.run()