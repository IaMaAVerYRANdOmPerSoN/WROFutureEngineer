from utils import cv2
from src.modules.config import Config
from utils.tools.base_tool import BaseTool
import numpy as np


# TODO: Integrate the lidar mp pipeline into the tool, and add diagnostics like point cloud density, noise levels, etc.
# Hopefully sooner than later though not my greatest priority tbh
class LiDARTool(BaseTool):
    def __init__(self):
        super().__init__(name="LiDAR", description="View LiDAR data and diagnostics")
        self.M = cv2.getRotationMatrix2D(
            (Config.CameraConfig.OUTPUT_WIDTH // 2, Config.CameraConfig.OUTPUT_HEIGHT // 2), 90, 1)

    def _draw_base(self, data, *args, **kwargs):
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        for point in data.points:
            # Scale and translate to fit in the frame
            x = int(point["x"] / 1000 * 250 + 250)
            # Invert y-axis and translate
            y = int(250 - point["y"] / 1000 * 250)
            confidence = point["confidence"]
            # More confident points are greener
            color = (0, confidence, 255 - confidence)
            cv2.circle(frame, (x, y), 3, color, -1)
        return frame

    def _draw(self, data, *args, **kwargs):
        frame = self._draw_base(data)
        cv2.imshow("LiDAR Feed", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        frame = self._draw_base(data)
        # rotate the frame on the x-axis by 90 degrees to simulate first-person view
        frame = cv2.warpAffine(frame, self.M, (frame.shape[1], frame.shape[0]))
        cv2.imshow("LiDAR Feed - No Perspective", frame)


async def run_lidar_tool():
    raise NotImplementedError(
        "Lidar interface is still under development, waiting on mechanical engineer to finalize the mount.")

    # tool = LiDARTool()
    # await tool.run()
