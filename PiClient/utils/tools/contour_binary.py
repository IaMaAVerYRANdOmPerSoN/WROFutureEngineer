"""Contour binary visualisation tool.

Displays detected contours as filled polygons on a neutral background
for high-contrast debugging.
"""

from utils import cv2, logger
from utils.tools.base_tool import BaseTool
import numpy as np
from src.modules.vision_processing import VisionObject

class ContourBinaryTool(BaseTool):
    """Tool for visualising contours as filled binary blobs.

    Renders detected objects as solid polygons on a dark grey background
    for maximum visibility, both with and without perspective transform.
    """
    def __init__(self):
        super().__init__(name="contourbinary", description="View contours detected by vision processing, displayed as filled binary blobs on neutral background for better visibility and debugging")
        self.color_map = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "green": (0, 200, 0),
            "red": (0, 0, 255),
            "blue": (255, 0, 0),
            "orange": (0, 165, 255),
            "magenta": (255, 0, 255),
        }

    def _draw_vision_object(self, object: VisionObject, color: tuple, frame):
        """Draw a filled polygon and centroid for a :class:`VisionObject`.

        :param object: The :class:`VisionObject` to draw.
        :param color: BGR colour tuple for the fill.
        :param frame: Target frame.
        """
        assert isinstance(frame, np.ndarray), logger.error(
            "Frame cannot be None")
        contour = object.contour
        if contour is not None:
            cv2.fillPoly(frame, [contour], color)
            cv2.circle(frame, (int(object.x_centroid),
                       int(object.y_centroid)), 3, color, -1)

    def _draw_base(self, data, frame, *args, **kwargs):
        """Core drawing logic for binary (filled-polygon) visualisation.

        :param data: Vision pipeline output tuple.
        :param frame: Target frame to draw on.
        :returns: The modified frame.
        """
        zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists = data

        if zone:
            self._draw_vision_object(zone, self.color_map.get(getattr(zone, "color", ""), (255, 255, 0)), frame)

        for wall in walls:
            self._draw_vision_object(wall, self.color_map.get(getattr(wall, "color", ""), (255, 255, 0)), frame)

        for obstacle in obstacles:
            self._draw_vision_object(obstacle, self.color_map.get(getattr(obstacle, "color", ""), (255, 255, 0)), frame)

        for line in corner_lines:
            self._draw_vision_object(line, self.color_map.get(getattr(line, "color", ""), (255, 255, 0)), frame)

        h, w = frame.shape[:2]
        cv2.line(frame, (w // 2, 0), (w // 2, h), (60, 60, 60), 1)

        status_lines = [
            f"WallDist L:{wall_dists['left']:.1f} R:{wall_dists['right']:.1f}",
            "ObstacleDist " +
            (", ".join(f"{side}:{dist:.1f}" for side, dist in obstacle_dists.items())
            if obstacle_dists else "none"),
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

    def _draw(self, data, *args, **kwargs):
        """Draw binary view with perspective-transformed data.

        :param data: Vision pipeline output tuple.
        """
        frame = np.full(self.frame.shape, (70, 70, 70), dtype=np.uint8)  # Dark background so the white of the zone is visible
        self._draw_base(data, frame, *args, **kwargs) # The contours are already in perspective-transformed coordinates, so we can draw them directly on the warped frame
        cv2.imshow("Contour Binary View", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        """Draw binary view without perspective transform.

        :param data: Vision pipeline output tuple.
        """
        frame = np.full(self.frame.shape, (70, 70, 70), dtype=np.uint8)
        self._draw_base(data, frame, *args, **kwargs) # Same drawing logic, just different data and window title
        cv2.imshow("Contour Binary View - No Perspective", frame)
    
async def run_contourbinary_tool():
    """Entry point for the contour binary visualisation tool."""
    tool = ContourBinaryTool()
    await tool.run()