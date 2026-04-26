from utils import cv2
from src.modules.config import Config
from utils.tools.base_tool import BaseTool
import numpy as np


class LiDARTool(BaseTool):
    def __init__(self):
        super().__init__(name="LiDAR", description="View LiDAR data and diagnostics")
        self.M = cv2.getRotationMatrix2D((Config.CameraConfig.OUTPUT_WIDTH // 2, Config.CameraConfig.OUTPUT_HEIGHT // 2), 90, 1)

    def _draw_base(self, data, *args, **kwargs):
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        for r, theta in data:
            x = r * np.cos(theta)
            y = r * np.sin(theta)
        cv2.circle(frame, (int(x) + frame.shape[1] // 2, int(y) + frame.shape[0] // 2), 3, (0, 255, 0), -1)
        return frame

    def _draw(self, data, *args, **kwargs):
        frame = self._draw_base(data)
        cv2.imshow("LiDAR Feed", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        frame = self._draw_base(data)
        frame = cv2.warpAffine(frame, self.M, (frame.shape[1], frame.shape[0])) # rotate the frame on the x-axis by 90 degrees to simulate first-person view
        cv2.imshow("LiDAR Feed - No Perspective", frame)

async def run_lidar_tool():
    raise NotImplementedError(
        "Lidar interface is still under development, waiting on mechanical engineer to finalize the mount.")
    
    # tool = LiDARTool()
    # await tool.run()