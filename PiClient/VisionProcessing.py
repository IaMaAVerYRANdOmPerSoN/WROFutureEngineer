import cv2
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence
from loguru import logger

class VisionObject():
    def __init__(self, contour):
        self.contour = contour
        self.area = cv2.contourArea(contour)

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

    def __find_blocks(self, masks):
        contours = []

        for mask in masks:
            contours.extend(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]),

        if contours:
            contours = [contour for contour in contours if len(contour) > 0]
            contours = sorted(contours, key=cv2.contourArea)
        else:
            return tuple()
        
        logger.info(f"Found contours: {contours}")
        return tuple(VisionObject(contour) for contour in contours)

    def find_obstacles(self, frame):
        logger.info("Searching for traffic signs...")
        uv = frame[:, :, 1:3]
        green_mask = cv2.inRange(uv, self.lower_green, self.upper_green)
        red_mask = cv2.inRange(uv, self.lower_red, self.upper_red)

        return self.__find_blocks([green_mask, red_mask])

    def check_corner_lines(self, frame):
        logger.info("Searching for turn aids...")
        uv = frame[:, :, 1:3]
        blue_mask = cv2.inRange(uv, self.lower_blue, self.upper_blue)
        orange_mask = cv2.inRange(uv, self.lower_orange, self.upper_orange)

        return self.__find_blocks([blue_mask, orange_mask])

    def check_field_bonds(self, frame):
        logger.info("Fetching drivable field bondaries...")

        y = frame[:, :, 0]
        white_mask = cv2.inRange(y, 200, 255)

        contours = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        if contours:
            walls = sorted(contours, key = cv2.contourArea)
        else:
            return None
    
    def find_walls(self, frame):
        logger.info("Checking for walls")

        y = frame[:, :, 0]
        black_mask = cv2.inRange(y, 0, 100)

        return self.__find_blocks(black_mask)
    
class AsyncVisionProcessor(VisionProcessor):
    def __init__(self, *args):
        super(AsyncVisionProcessor, self).__init__(*args)
        self.executor = None
        self.loop = asyncio.get_event_loop()

    async def __aenter__(self):
        self.executor = ThreadPoolExecutor(8)
        return self

    async def __aexit__(self, *args): # Error handling in main loop
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    async def find_obstacles(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).find_obstacles, frame)
    
    async def check_field_bonds(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).check_field_bonds, frame)
    
    async def check_corner_lines(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncVisionProcessor, self).check_corner_lines, frame)