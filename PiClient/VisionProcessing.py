import cv2
import numpy as np
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Sequence
from loguru import logger

class VisionObject():
    def __init__(self, color, contour):
        self.contour = contour
        self.area = cv2.contourArea(contour)
        self.color = color

        self.bbox = cv2.boundingRect(contour)
        x, y, w, h = self.bbox
        self.x_centroid = x + w/2
        self.y_centroid = y + h/2
        self.bottom_y = y + h # Use this to find closest object
        
class VisionProcessor(): 
    def __init__(self):
        self.lower_orange = np.array([33, 194])
        self.upper_orange = np.array([73, 234])

        self.lower_blue = np.array([216, 63])
        self.upper_blue = np.array([255, 103])

        self.lower_green = np.array([0, 0])
        self.upper_green = np.array([110, 110])

        self.lower_red = np.array([100, 140])
        self.upper_red = np.array([130, 255])

    def __find_blocks(self, masks, colors):
        all_detected = []

        for mask, color in zip(masks, colors):
            contours, *_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            all_detected.extend([(color, contour) for contour in contours if cv2.contourArea(contour) > 50])

        if not all_detected:
            return tuple()
        
        all_detected.sort(key=lambda i: cv2.contourArea(i[1]), reverse=True)
        
        logger.info(f"Detected {len(all_detected)} objects.")
        return tuple(VisionObject(color, contour) for color, contour in all_detected)

    def find_obstacles(self, frame):
        logger.info("Searching for traffic signs...")
        uv = frame[:, :, 1:3]
        green_mask = cv2.inRange(uv, self.lower_green, self.upper_green)
        red_mask = cv2.inRange(uv, self.lower_red, self.upper_red)

        return self.__find_blocks([green_mask, red_mask], ["green", "red"])

    def check_corner_lines(self, frame):
        logger.info("Searching for turn aids...")
        uv = frame[:, :, 1:3]
        blue_mask = cv2.inRange(uv, self.lower_blue, self.upper_blue)
        orange_mask = cv2.inRange(uv, self.lower_orange, self.upper_orange)

        return self.__find_blocks([blue_mask, orange_mask], ["blue", "orange"])

    def check_field_bonds(self, frame):
        logger.info("Fetching drivable field bondaries...")

        y = frame[:, :, 0]
        white_mask = cv2.inRange(y, 200, 255)

        contours, *_ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            drivable_area = max(contours, key=cv2.contourArea)
        else:
            return None
        
        return VisionObject("white", drivable_area)
    
    def find_walls(self, frame):
        logger.info("Checking for walls")

        y = frame[:, :, 0]
        black_mask = cv2.inRange(y, 0, 100)

        return self.__find_blocks(black_mask)
    
    def get_distance(self,  items: Sequence[VisionObject], frame_width = 160):
        center_x = frame_width // 2

        dists = []

        if not items:
            return len(items) * [float("inf")]
        
        for item in items: # Should already be sorted
            if item.x_centroid >= center_x and item.y_centroid > 30: # Wall on the right, get left edge, crop to bottom ROI
                x, *_ = item.bbox
                dists.append(x - center_x)
            if item.x_centroid < center_x and item.y_centroid > 30: # Wall on the left, get right edge, crop to bootom ROI
                x, _, w, _ = item.bbox
                dists.append(center_x - (x + w))

        return dists

    def get_wall_distance(self, items: Sequence[VisionObject], frame_width = 160):
        center_x = frame_width // 2

        wall_dists = {
            "left": float("inf"),
            "right": float("inf")
        }

        if not items:
            return wall_dists

        for item in items:
            if item.x_centroid >= center_x and item.y_centroid > 30: # Wall on the right, get left edge, crop to bottom ROI
                x, *_ = item.bbox
                wall_dists["right"] = x - center_x
            if item.x_centroid < center_x and item.y_centroid > 30: # Wall on the left, get right edge, crop to bootom ROI
                x, _, w, _ = item.bbox
                wall_dists["left"] = center_x - (x + w)

        return wall_dists
        
    
class AsyncVisionProcessor(VisionProcessor):
    def __init__(self, *args):
        super(AsyncVisionProcessor, self).__init__(*args)
        self.executor = None
        self.loop = asyncio.get_event_loop()

    async def __aenter__(self):
        self.executor = ProcessPoolExecutor(1)
        return self

    async def __aexit__(self, *args): # Error handling in main loop
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    async def find_obstacles(self, frame) -> tuple[VisionObject]:
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).find_obstacles, frame)
    
    async def check_field_bonds(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).check_field_bonds, frame)
    
    async def check_corner_lines(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).check_corner_lines, frame)
    
    async def get_distance(self, items: Sequence[VisionObject], frame_width=160):
        return await self.loop.run_in_executor(self.executor, super().get_distance, items, frame_width)
    
    async def get_wall_distance(self, walls: Sequence[VisionObject], frame_width=160):
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).get_wall_distance, walls, frame_width)
    
    async def comprehensive_analysis(self, frame):
        def work(f):
            zone, walls, obstacles, corner_lines = (
                super(AsyncVisionProcessor, self).check_field_bonds(f),
                super(AsyncVisionProcessor, self).find_walls(f),
                super(AsyncVisionProcessor, self).find_obstacles(f),
                super(AsyncVisionProcessor, self).check_corner_lines(f),
            )

            wall_dists = super(AsyncVisionProcessor, self).get_wall_distance(walls)
            obstacle_dists = super(AsyncVisionProcessor, self).get_distance(obstacles)

            return zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists
        
        return await self.loop.run_in_executor(self.executor, work, frame)