"""Open Challenge vision processor.

Extends :class:`VisionProcessor` with wall-distance measurement using
left/right regions of interest.
"""

from src.modules.vision.data import Walls
from src.modules.vision.base import VisionProcessor
from src.modules.lib.config import Config
import numpy as np
import cv2

class OpenChallengeVisionProcessor(VisionProcessor):
    """Vision processor specialised for the Open Challenge.

    Measures normalised black-pixel density in left and right ROIs
    to estimate wall distances.

    :cvar LEFT_WALL_ROI: Region-of-interest slice for the left wall.
    :cvar RIGHT_WALL_ROI: Region-of-interest slice for the right wall.
    """
    LEFT_WALL_ROI = Config.VisionConfig.LEFT_WALL_ROI
    RIGHT_WALL_ROI = Config.VisionConfig.RIGHT_WALL_ROI

    def __init__(self, *args, **kwargs):
        """Initialise the Open Challenge vision processor.

        Forwards all arguments to :class:`VisionProcessor`.
        """
        return super(OpenChallengeVisionProcessor, self).__init__(*args, **kwargs)
        
    def get_normalized_relative_wall_distances(self, frame: np.ndarray):
        """Compute normalised wall distances from a preprocessed frame.

        Applies colour thresholding to the left and right ROIs and counts
        non-zero (black) pixels, returning a :class:`Walls` instance.

        :param frame: Preprocessed HSV frame.
        :returns: Normalised wall distances.
        :rtype: Walls
        """
        left_area = frame[self.LEFT_WALL_ROI]
        right_area = frame[self.RIGHT_WALL_ROI]

        left_masked = cv2.inRange(left_area, self.LOWER_BLACK, self.UPPER_BLACK)
        right_masked = cv2.inRange(right_area, self.LOWER_BLACK, self.UPPER_BLACK)

        left_pixels = cv2.countNonZero(left_masked)
        right_pixels = cv2.countNonZero(right_masked)
        
        return Walls(left_pixels, right_pixels, left_area.shape[0] * left_area.shape[1])