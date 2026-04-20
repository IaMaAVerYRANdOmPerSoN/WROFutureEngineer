import cv2

from utils.tools.base_tool import BaseTool

class RawTool(BaseTool):
    def __init__(self):
        super().__init__(name="raw", description="View raw camera feed and vision processing output without perspective transformation")
        self.color_map = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "green": (0, 200, 0),
            "red": (0, 0, 255),
            "blue": (255, 0, 0),
            "orange": (0, 165, 255),
        }

    def _draw(self, data, *args, **kwargs):
        zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists = data
        frame = self.frame

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

        cv2.imshow("Raw Tool", frame)
    
    def _draw_no_perspective(self, data, *args, **kwargs):
        self._draw(data, *args, **kwargs) # Drawing method is the same, the data simply has no perspective transformation applied
    
async def run_raw_tool():
    tool = RawTool()
    await tool.run()