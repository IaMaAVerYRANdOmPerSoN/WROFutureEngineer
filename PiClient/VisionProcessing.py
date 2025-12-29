import cv2
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

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
        pass # Not sure what to put here yet

    def find_obstacles(self, frame):
        uv = np.ascontiguousarray(frame[:, :, 1:3])
        
        green_mask = cv2.inRange(uv, (0, 0), (110, 110)) # Green: Low U and Low V
        
        red_mask = cv2.inRange(uv, (100, 140), (130, 255)) # Red: High V; Cap U to 130 to exclude Magenta
        
        magenta_mask = cv2.inRange(uv, (150, 150), (255, 255)) # Magneta: High U and V

        contours = {
            "green": cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            "red": cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            "magenta": cv2.findContours(magenta_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        }

        contours = {color: contour for color, contour in contours.items() if len(contour) > 0}

        return {
            "green" : [VisionObject(contour) for contour in contours.get("green")],
            "red" : [VisionObject(contour) for contour in contours.get("red")],
            "magenta": [VisionObject(contour) for contour in contours.get("magenta")]
        }

    def check_field_bonds(self, frame):
        y = np.ascontiguousarray(frame[:, :, 0])

        white_mask = cv2.inRange(y, (200, 255))

        contours = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        contigous_field_bondary = max(contours, key = cv2.contourArea)
        return VisionObject(contigous_field_bondary)
    
    def check_corner_markers(self, frame):
        raise NotImplementedError 
    
class AynscVisionProcessor(VisionProcessor):
    def __init__(self, *args):
        super.__init__(*args)
        self.executor = ThreadPoolExecutor(10)
        self.loop = asyncio.get_event_loop()

    async def find_obstacles(self, frame):
        return await self.loop.run_in_executor(self.executor, super().find_obstacles, frame)
    
    async def check_field_bonds(self, frame):
        return await self.loop.run_in_executor(self.executor, super().check_field_bonds, frame)
    
    async def check_corner_markers(self, frame):
        return await self.loop.run_in_executor(self.executor, super().check_corner_markers, frame)