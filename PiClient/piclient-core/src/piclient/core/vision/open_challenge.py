"""Open Challenge vision processor.

Extends :class:`VisionProcessor` with wall-distance measurement using
left/right regions of interest.
"""

from .data import Walls
from .base import VisionProcessor
from ..lib import GLOBAL_CONFIG, export
import numpy as np
import cv2

from typing import Any


@export
class OpenChallengeVisionProcessor(VisionProcessor):
    """Vision processor specialised for the Open Challenge.

    Measures normalised black-pixel density in left and right ROIs
    to estimate wall distances.

    :ivar left_wall_roi: Region-of-interest slice for the left wall.
    :ivar right_wall_roi: Region-of-interest slice for the right wall.
    """

    _DEFAULT_LEFT_WALL_ROI = GLOBAL_CONFIG().VisionConfig.LEFT_WALL_ROI
    _DEFAULT_RIGHT_WALL_ROI = GLOBAL_CONFIG().VisionConfig.RIGHT_WALL_ROI

    def __init__(self, left_wall_roi: tuple[slice, slice] | None = None, right_wall_roi: tuple[slice, slice] | None = None, *args: Any, **kwargs: Any):
        """Initialise the Open Challenge vision processor.

        Forwards most arguments to :class:`VisionProcessor`.  Accepts
        optional keyword-only overrides for the wall ROIs.

        :param left_wall_roi: NumPy slice for the left wall (default from Config).
        :param right_wall_roi: NumPy slice for the right wall (default from Config).
        """
        super(OpenChallengeVisionProcessor, self).__init__(*args, **kwargs)
        self.left_wall_roi = (
            left_wall_roi
            if left_wall_roi is not None
            else self._DEFAULT_LEFT_WALL_ROI
        )
        self.right_wall_roi = (
            right_wall_roi
            if right_wall_roi is not None
            else self._DEFAULT_RIGHT_WALL_ROI
        )

    def get_normalized_relative_wall_distances(self, frame: np.ndarray):
        """Compute normalised wall distances from a preprocessed frame.

        Applies colour thresholding to the left and right ROIs and counts
        non-zero (black) pixels, returning a :class:`Walls` instance.

        :param frame: Preprocessed HSV frame.
        :returns: Normalised wall distances.
        :rtype: Walls
        """
        left_area = frame[self.left_wall_roi]
        right_area = frame[self.right_wall_roi]

        left_masked = cv2.inRange(
            left_area, self.lower_black, self.upper_black)
        right_masked = cv2.inRange(
            right_area, self.lower_black, self.upper_black)

        left_pixels = cv2.countNonZero(left_masked)
        right_pixels = cv2.countNonZero(right_masked)

        return Walls(left_pixels, right_pixels, left_area.shape[0] * left_area.shape[1])
