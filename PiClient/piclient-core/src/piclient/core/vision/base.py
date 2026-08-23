"""Base vision processor.

Provides :class:`VisionProcessor` with common preprocessing, perspective
transform, and contour-finding utilities.
"""


from collections.abc import Sequence, Callable

import cv2
import numpy as np

from loguru import logger
from ..lib import GLOBAL_CONFIG, export
from .data import VisionObject


@export
class VisionProcessor:
    """Base class for vision processing pipelines.

    Handles HSV conversion, perspective transforms, and contour
    extraction from colour masks.

    :ivar perspective_transform: Homography matrix for contour warping.
    :ivar lower_black: Lower HSV bound for black/line detection.
    :ivar upper_black: Upper HSV bound for black/line detection.
    :ivar use_transform: Whether to apply perspective transform to contours.
    """

    # class-level defaults (overridden per-instance via __init__)
    _DEFAULT_PERSPECTIVE_TRANSFORM: np.ndarray[tuple[int, ...], np.dtype[np.float32 | np.float64]] = np.array(
        GLOBAL_CONFIG().VisionConfig.PERSPECTIVE_TRANSFORM, dtype=np.float32)
    _DEFAULT_INITIAL_ROI: tuple[slice, slice,
                                slice] = GLOBAL_CONFIG().CameraConfig.INITIAL_ROI
    _DEFAULT_LOWER_BLACK: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.array(
        GLOBAL_CONFIG().VisionConfig.LOWER_BLACK, dtype=np.uint8)
    _DEFAULT_UPPER_BLACK: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.array(
        GLOBAL_CONFIG().VisionConfig.UPPER_BLACK, dtype=np.uint8)

    def __init__(
        self,
        use_transform: bool = False,
        *,
        perspective_transform: np.ndarray[
            tuple[int, ...],
            np.dtype[np.float32 | np.float64]
        ] | None = None,
        src: np.ndarray[
            tuple[int, ...],
            np.dtype[np.float32 | np.float64]
        ] | None = None,
        dst: np.ndarray[
            tuple[int, ...],
            np.dtype[np.float32 | np.float64]
        ] | None = None,
        initial_roi: tuple[slice, slice, slice] | None = None,
        lower_black: np.ndarray[tuple[int, ...],
                                np.dtype[np.uint8]] | None = None,
        upper_black: np.ndarray[tuple[int, ...],
                                np.dtype[np.uint8]] | None = None,
    ) -> None:
        """Initialise the vision processor.

        :param use_transform: If ``True``, apply perspective transform to detected contours.
        :param perspective_transform: 3x3 homography matrix (default from Config).
        :param src: 4x2 source points to compute a homography from.
        :param dst: 4x2 destination points to compute a homography from.
        :param initial_roi: NumPy slice for the initial crop (default from Config).
        :param lower_black: Lower HSV bound for black detection (default from Config).
        :param upper_black: Upper HSV bound for black detection (default from Config).
        """
        self.use_transform: bool = use_transform
        if (perspective_transform and src) or (src and not dst) or (dst and not src):
            raise ValueError(
                "Cannot have both perspective_transform and src/dst, or only one of src/dst")
        elif perspective_transform:
            self.perspective_transform: np.ndarray[tuple[int, ...],
                                                   np.dtype[np.float32 | np.float64]] = perspective_transform
        elif src and dst:
            self.perspective_transform = self.get_perspective_transform(
                src, dst)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            self.perspective_transform = self._DEFAULT_PERSPECTIVE_TRANSFORM

        self.initial_roi: tuple[slice, slice, slice] = (
            initial_roi
            if initial_roi is not None
            else self._DEFAULT_INITIAL_ROI
        )
        self.lower_black: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = (
            lower_black
            if lower_black is not None
            else self._DEFAULT_LOWER_BLACK
        )
        self.upper_black: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = (
            upper_black
            if upper_black is not None
            else self._DEFAULT_UPPER_BLACK
        )

    def _preprocess(self, frame: np.ndarray[tuple[int, ...], np.dtype[np.uint8]]) -> np.ndarray[tuple[int, ...], np.dtype[np.uint8]]:
        """Convert a BGR frame to HSV.

        :param frame: Raw BGR frame as a numpy array.
        :returns: Preprocessed HSV frame.
        """
        return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.uint8)

    def preprocess(self, frame: np.ndarray[tuple[int, ...], np.dtype[np.uint8]]) -> np.ndarray[tuple[int, ...], np.dtype[np.uint8]]:
        """Convert one camera frame into the representation used by vision stages.

        This public wrapper delegates to :meth:`_preprocess`, preserving a
        single extension point for subclasses while exposing the standard
        preprocessing operation to callers.

        :param frame: BGR camera frame as an unsigned 8-bit NumPy array.
        :returns: HSV frame with the same spatial dimensions as *frame*.
        :rtype: numpy.ndarray
        """
        return self._preprocess(frame)

    # Applying cv2.perspectiveTransform is much more efficient than warping whole frame
    def _perspective_transform(self, contours_and_colors: Sequence[tuple[str, np.ndarray]]) -> tuple[VisionObject, ...]:
        """Apply perspective transform to contours and wrap them in :class:`VisionObject`.

        :param contours_and_colors: Sequence of ``(color, contour)`` pairs.
            Each contour is an OpenCV array and each color labels it.
        :returns: tuple of :class:`VisionObject` instances.
        """
        if not self.use_transform:
            return tuple(VisionObject(contour=contour, color=color) for color, contour in contours_and_colors)
        return tuple(VisionObject(contour=cv2.perspectiveTransform(contour, self.perspective_transform), color=color) for color, contour in contours_and_colors)

    @staticmethod
    def simplify_contour(contour: np.ndarray[tuple[int, int], np.dtype[np.int32]], epsilon_factor: float = 0.015) -> np.ndarray[tuple[int, int], np.dtype[np.int32]]:
        """Reduce a contour to a smaller polygon using Ramer-Douglas-Peucker.

        The approximation tolerance is proportional to the contour perimeter,
        so the same factor scales with objects of different sizes.

        :param contour: OpenCV contour represented by integer ``(x, y)`` points.
        :param epsilon_factor: Perimeter multiplier used as approximation
            tolerance; larger values produce fewer vertices.
        :returns: Approximated contour reshaped as an ``(N, 2)`` array.
        :rtype: numpy.ndarray
        """
        epsilon = epsilon_factor * cv2.arcLength(contour, True)
        vertices: np.ndarray[tuple[int, int], np.dtype[np.int32]] = cv2.approxPolyDP(contour, epsilon, True).astype(
            # Simplify geometry to reduce vertices for performance
            np.int32).reshape(-1, 2)
        return vertices

    def _find_blocks(self, masks: Sequence[np.ndarray], colors: Sequence[str], simplify: bool = True, key: Callable[[tuple[str, np.ndarray]], float] = lambda x: cv2.contourArea(x[1]), min_area: int = 300, max_results: int = 10) -> tuple[VisionObject, ...]:
        """Extract contours from binary masks and return sorted :class:`VisionObject` instances.

        Filters small contours, sorts by area (largest first), and limits
        to the top 10 results.

        :param masks: List of binary masks (numpy arrays).
        :param colors: List of colour labels matching each mask.
        :param simplify: If ``True``, simplify contours to reduce vertices.
        :param key: Optional sorting key function (default is contour area).
        :param min_area: Minimum contour area to keep (default 300).
        :param max_results: Maximum number of contours to return (default 10).
        :returns: tuple of :class:`VisionObject` instances, may be empty.
        """
        contours: list[tuple[str, np.ndarray]] = []

        for mask, color in zip(masks, colors):
            detected_contours, * \
                _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if detected_contours:
                contours.extend([(color, contour)
                                for contour in detected_contours])
        if not contours:
            return tuple()

        # Filter out small contours that are likely noise, tuned for 512x384 resolution
        contours = [
            (color, self.simplify_contour(contour) if simplify else contour)
            for color, contour in contours
            if cv2.contourArea(contour) > min_area
        ]
        contours.sort(key=key, reverse=True)  # Biggest object first
        # Limit to max_results largest contours to reduce noise
        contours = contours[:max_results if max_results else None]

        logger.info(f"Detected {len(contours)} objects.")
        return self._perspective_transform(contours)

    @staticmethod
    def get_perspective_transform(src: np.ndarray, dst: np.ndarray) -> cv2.typing.MatLike | np.ndarray[tuple[int, ...], np.dtype[np.float32 | np.float64]]:
        """Compute a perspective-transform matrix from source to destination points.

        :param src: Four source points defining the original quadrilateral.
        :param dst: Four destination points defining the transformed
            quadrilateral.

        :returns: 3x3 perspective transform matrix.
        :rtype: np.ndarray
        """

        return cv2.getPerspectiveTransform(src, dst)
