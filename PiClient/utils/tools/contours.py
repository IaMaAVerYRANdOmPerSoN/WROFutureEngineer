"""Contours visualisation tool.

Displays the camera feed with detected contours overlaid, both with
and without perspective transformation.
"""

from utils import cv2
from src.piclient.lib.config import Config
from utils.tools.base_tool import BaseTool

class ContoursTool(BaseTool):
    """Tool for visualising detected contours and vision metadata.

    Draws zones, walls, obstacles, and corner lines on the camera feed,
    along with wall-distance and obstacle-distance readouts.
    """
    def __init__(self):
        super().__init__(name="contours", description="View camera feed with contours and vision processing output with and without perspective transformation")
        self.color_map = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "green": (0, 200, 0),
            "red": (0, 0, 255),
            "blue": (255, 0, 0),
            "orange": (0, 165, 255),
        }

    def _draw_base(self, data, frame, *args, **kwargs):
        """Core drawing logic shared by perspective and no-perspective views.

        Draws detected objects and overlays status text (wall distances,
        obstacle distances) on the given frame.

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
        """Draw perspective-transformed view with contour overlays.

        :param data: Vision pipeline output tuple.
        """
        frame = cv2.warpPerspective(self.frame, Config.VisionConfig.PERSPECTIVE_TRANSFORM, (self.frame.shape[1], self.frame.shape[0]))
        self._draw_base(data, frame, *args, **kwargs) # The contours are already in perspective-transformed coordinates, so we can draw them directly on the warped frame
        cv2.imshow("Feed with contours", frame)

    def _draw_no_perspective(self, data, *args, **kwargs):
        """Draw raw (unwarped) view with contour overlays.

        :param data: Vision pipeline output tuple.
        """
        frame = self.frame.copy()
        self._draw_base(data, frame, *args, **kwargs) # Same drawing logic, just different data and window title
        cv2.imshow("Before Perspective Transformation", frame)
    
async def run_contours_tool():
    """Entry point for the contours visualisation tool."""
    tool = ContoursTool()
    await tool.run()