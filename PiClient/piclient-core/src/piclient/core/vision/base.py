"""Base vision processor.

Provides :class:`VisionProcessor` with common preprocessing, perspective
transform, and contour-finding utilities.
"""

from ..lib import Config, export
import numpy as np
import cv2
from .data import VisionObject
from .. import logger
from typing import Sequence, Tuple


@export
class VisionProcessor:
    """Base class for vision processing pipelines.

    Handles HSV conversion, ROI cropping, perspective transforms,
    and contour extraction from colour masks.

    :cvar PERSPECTIVE_TRANSFORM: Homography matrix from config.
    :cvar INITIAL_ROI: Region-of-interest slice applied during preprocessing.
    :cvar LOWER_BLACK: Lower HSV bound for black/line detection.
    :cvar UPPER_BLACK: Upper HSV bound for black/line detection.
    :ivar use_transform: Whether to apply perspective transform to contours.
    :ivar frame: Most recently preprocessed frame.
    """
    PERSPECTIVE_TRANSFORM = np.array(
        (Config.VisionConfig.PERSPECTIVE_TRANSFORM), dtype=np.float32)
    
    INITIAL_ROI = Config.VisionConfig.INITIAL_ROI
    
    LOWER_BLACK = np.array(
        Config.VisionConfig.LOWER_BLACK, dtype=np.uint8)
    UPPER_BLACK = np.array(
        Config.VisionConfig.UPPER_BLACK, dtype=np.uint8)

    def __init__(self, use_transform: bool = False):
        """Initialise the vision processor.

        :param use_transform: If ``True``, apply perspective transform to detected contours.
        """
        self.use_transform = use_transform
        self.frame = None

    def _preprocess(self, frame: np.ndarray):
        """Convert a BGR frame to HSV and apply the initial ROI.

        :param frame: Raw BGR frame as a numpy array.
        :returns: Preprocessed HSV frame cropped to :attr:`INITIAL_ROI`.
        """
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[self.INITIAL_ROI]
        return frame

    # Applying cv2.perspectiveTransform is much more efficient than warping whole frame
    def _perspective_transform(self, contours: Sequence, colors: Sequence[str]) -> Tuple[VisionObject, ...]:
        """Apply perspective transform to contours and wrap them in :class:`VisionObject`.

        :param contours: List of OpenCV contours.
        :param colors: List of colour labels matching each contour.
        :returns: Tuple of :class:`VisionObject` instances.
        """
        if not self.use_transform:
            return tuple(VisionObject(contour=contour, color = color) for contour, color, in zip(contours, colors))
        return tuple(VisionObject(contour=cv2.perspectiveTransform(contour, VisionProcessor.PERSPECTIVE_TRANSFORM), color=color) for contour, color in zip(contours, colors))

    def _find_blocks(self, masks, colors):
        """Extract contours from binary masks and return sorted :class:`VisionObject` instances.

        Filters small contours, sorts by area (largest first), and limits
        to the top 10 results.

        :param masks: List of binary masks (numpy arrays).
        :param colors: List of colour labels matching each mask.
        :returns: Tuple of :class:`VisionObject` instances, may be empty.
        """
        contours = []
        detected_colors = []

        for mask, color in zip(masks, colors):
            detected_contours, * \
                _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if detected_contours:
                contours.extend(detected_contours)
                detected_colors.extend([color] * len(detected_contours))

        if not contours:
            return tuple()

        contours = [contour for contour in contours if cv2.contourArea(contour) > 120 ] # Filter out small contours that are likely noise, tuned for 512x384 resolution
        contours.sort(key=lambda contour: cv2.contourArea(contour), reverse=True) # Biggest object first
        contours = contours[:10] # Limit to 10 largest contours to reduce noise

        logger.info(f"Detected {len(contours)} objects.")
        return self._perspective_transform(contours, detected_colors)
        # Okay so I this is a pragmatic solution because I only have to change a single method to apply perspective transforms globally. Also way faster then warping whole frame.
    
    @staticmethod
    def get_perspective_transform():
        """Compute a perspective-transform matrix from source to destination points.

        Currently returns identity (placeholder). Override source/destination
        arrays with calibrated corner coordinates.

        :returns: 3x3 perspective transform matrix.
        :rtype: np.ndarray
        """
        src = np.array([
            [0, 0],
            [0, 0],
            [0, 0],
            [0, 0],
        ], dtype=np.float32)
        dst = np.array([
            [0, 0],
            [0, 0],
            [0, 0],
            [0, 0],
        ], dtype=np.float32)

        return cv2.getPerspectiveTransform(src, dst)