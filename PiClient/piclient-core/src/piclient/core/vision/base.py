"""Base vision processor.

Provides :class:`VisionProcessor` with common preprocessing, perspective
transform, and contour-finding utilities.
"""

from ..lib import Config, export
import numpy as np
import cv2
from .data import VisionObject
from .. import logger
from collections.abc import Sequence


@export
class VisionProcessor:
    """Base class for vision processing pipelines.

    Handles HSV conversion, ROI cropping, perspective transforms,
    and contour extraction from colour masks.

    :ivar perspective_transform: Homography matrix for contour warping.
    :ivar initial_roi: Region-of-interest slice applied during preprocessing.
    :ivar lower_black: Lower HSV bound for black/line detection.
    :ivar upper_black: Upper HSV bound for black/line detection.
    :ivar use_transform: Whether to apply perspective transform to contours.
    """

    # class-level defaults (overridden per-instance via __init__)
    _DEFAULT_PERSPECTIVE_TRANSFORM = np.array(
        Config.VisionConfig.PERSPECTIVE_TRANSFORM, dtype=np.float32)
    _DEFAULT_INITIAL_ROI = Config.VisionConfig.INITIAL_ROI
    _DEFAULT_LOWER_BLACK = np.array(
        Config.VisionConfig.LOWER_BLACK, dtype=np.uint8)
    _DEFAULT_UPPER_BLACK = np.array(
        Config.VisionConfig.UPPER_BLACK, dtype=np.uint8)

    def __init__(
        self,
        use_transform: bool = False,
        *,
        perspective_transform: np.ndarray | None = None,
        src: np.ndarray | None = None,
        dst: np.ndarray | None = None,
        initial_roi: tuple[slice, slice, slice] | None = None,
        lower_black: np.ndarray | None = None,
        upper_black: np.ndarray | None = None,
    ):
        """Initialise the vision processor.

        :param use_transform: If ``True``, apply perspective transform to detected contours.
        :param perspective_transform: 3x3 homography matrix (default from Config).
        :param src: 4x2 source points to compute a homography from.
        :param dst: 4x2 destination points to compute a homography from.
        :param initial_roi: NumPy slice for the initial crop (default from Config).
        :param lower_black: Lower HSV bound for black detection (default from Config).
        :param upper_black: Upper HSV bound for black detection (default from Config).
        """
        self.use_transform = use_transform
        if (perspective_transform and src) or (src and not dst) or (dst and not src):
            raise ValueError(
                "Cannot have both perspective_transform and src/dst, or only one of src/dst")
        elif perspective_transform:
            self.perspective_transform = perspective_transform
        elif src and dst:
            self.perspective_transform = self.get_perspective_transform(
                src, dst)
        else:
            self.perspective_transform = self._DEFAULT_PERSPECTIVE_TRANSFORM
        self.initial_roi = (
            initial_roi if initial_roi is not None else self._DEFAULT_INITIAL_ROI
        )
        self.lower_black = (
            lower_black if lower_black is not None else self._DEFAULT_LOWER_BLACK
        )
        self.upper_black = (
            upper_black if upper_black is not None else self._DEFAULT_UPPER_BLACK
        )

    def _preprocess(self, frame: np.ndarray):
        """Convert a BGR frame to HSV and apply the initial ROI.

        :param frame: Raw BGR frame as a numpy array.
        :returns: Preprocessed HSV frame cropped to :attr:`initial_roi`.
        """
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[self.initial_roi]
        return frame

    # Applying cv2.perspectiveTransform is much more efficient than warping whole frame
    def _perspective_transform(self, contours: Sequence[np.ndarray], colors: Sequence[str]) -> tuple[VisionObject, ...]:
        """Apply perspective transform to contours and wrap them in :class:`VisionObject`.

        :param contours: List of OpenCV contours.
        :param colors: List of colour labels matching each contour.
        :returns: tuple of :class:`VisionObject` instances.
        """
        if not self.use_transform:
            return tuple(VisionObject(contour=contour, color=color) for contour, color, in zip(contours, colors))
        return tuple(VisionObject(contour=cv2.perspectiveTransform(contour, self.perspective_transform), color=color) for contour, color in zip(contours, colors))

    def _find_blocks(self, masks: list[np.ndarray], colors: list[str]) -> tuple[VisionObject, ...]:
        """Extract contours from binary masks and return sorted :class:`VisionObject` instances.

        Filters small contours, sorts by area (largest first), and limits
        to the top 10 results.

        :param masks: List of binary masks (numpy arrays).
        :param colors: List of colour labels matching each mask.
        :returns: tuple of :class:`VisionObject` instances, may be empty.
        """
        contours: list[np.ndarray] = []
        detected_colors: list[str] = []

        for mask, color in zip(masks, colors):
            detected_contours, * \
                _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if detected_contours:
                contours.extend(detected_contours)
                detected_colors.extend([color] * len(detected_contours))

        if not contours:
            return tuple()

        # Filter out small contours that are likely noise, tuned for 512x384 resolution
        contours = [
            contour for contour in contours if cv2.contourArea(contour) > 120]
        contours.sort(key=lambda contour: cv2.contourArea(
            contour), reverse=True)  # Biggest object first
        # Limit to 10 largest contours to reduce noise
        contours = contours[:10]

        logger.info(f"Detected {len(contours)} objects.")
        return self._perspective_transform(contours, detected_colors)
        # Okay so I this is a pragmatic solution because I only have to change a single method to apply perspective transforms globally. Also way faster then warping whole frame.

    @staticmethod
    def get_perspective_transform(src: np.ndarray, dst: np.ndarray):
        """Compute a perspective-transform matrix from source to destination points.

        :param: src: 4x2 matrix of source points.
        :param: dst: 4x2 matrix of destination points.

        :returns: 3x3 perspective transform matrix.
        :rtype: np.ndarray
        """

        return cv2.getPerspectiveTransform(src, dst)
