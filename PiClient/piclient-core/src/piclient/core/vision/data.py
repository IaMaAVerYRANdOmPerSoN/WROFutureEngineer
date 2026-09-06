"""Vision data structures.

Defines dataclasses for vision data, including detected objects, open challenge interfaces, and obstacle challenge interfaces.
"""
from typing import cast

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from ..lib import export


def get_pose(contour: np.ndarray) -> tuple[float, float, float]:
    """Calculate a contour's centroid and principal-axis angle.

    :param contour: OpenCV contour with shape ``(N, 1, 2)``.
    :returns: ``(x, y, theta)`` where ``theta`` is the principal-axis angle in
        degrees.
    """
    M = cv2.moments(contour)
    if M["m00"] == 0:
        return 0.0, 0.0, 0.0
    x_centroid = M["m10"] / M["m00"]
    y_centroid = M["m01"] / M["m00"]
    theta = 0.5 * np.arctan2(2 * M["mu11"], M["mu20"] - M["mu02"])
    return x_centroid, y_centroid, np.rad2deg(theta)


@export
@dataclass(slots=True)
class VisionObject:
    """A detected object in the camera frame.

    Wraps an OpenCV contour with colour metadata and derived properties
    (bounding box, centroid coordinates).

    :ivar contour: OpenCV contour (Nx1x2 array of points).
    :ivar color: Colour label string (e.g. ``"green"``, ``"red"``).
    :ivar bbox: Bounding rectangle ``(x, y, width, height)``. Values are pixel
        coordinates until a :class:`ParkingLot` normalises them.
    :ivar x_centroid: X coordinate of the contour centroid, in pixels unless
        normalised by :class:`ParkingLot`.
    :ivar y_centroid: Y coordinate of the contour centroid, in pixels unless
        normalised by :class:`ParkingLot`.
    :ivar rotation: Principal-axis angle scaled from degrees to the range
        ``[-1, 1]`` by dividing by 90.
    """
    contour: np.ndarray
    color: str
    bbox: tuple[float, float, float, float] = None # pyright: ignore[reportAssignmentType]
    x_centroid: float = None  # pyright: ignore[reportAssignmentType]
    y_centroid: float = None  # pyright: ignore[reportAssignmentType]
    rotation: float = None  # pyright: ignore[reportAssignmentType]

    def __post_init__(self) -> None:
        """Derive the bounding box, centroid, and normalised rotation in place."""
        # Added custom type stub, default type stubs use Sequence[int]
        self.bbox = cast(tuple[float, float, float, float],
                         cv2.boundingRect(self.contour))
        self.x_centroid, self.y_centroid, self.rotation = get_pose(
            self.contour)
        self.x_centroid = float(self.x_centroid)
        self.y_centroid = float(self.y_centroid)
        self.rotation = float(np.clip(self.rotation / 90.0, -1.0, 1.0))


@export
@dataclass(slots=True)
class Walls:
    """Normalised wall-distance measurements.

    Values are black-pixel counts divided by the corresponding ROI area; they
    are fill ratios, not physical distances.

    :ivar left: Left ROI black-pixel fill ratio, normally in ``[0, 1]``.
    :ivar right: Right ROI black-pixel fill ratio, normally in ``[0, 1]``.
    :ivar center: Center ROI black-pixel fill ratio, normally in ``[0, 1]``.
    :ivar area: Denominator (pixel area) for the left and right ratios.
    :ivar center_area: Denominator (pixel area) for the center ratio.
    """
    left: float
    right: float
    center: float
    area: float
    center_area: float

    def __post_init__(self) -> None:
        """Replace raw black-pixel counts with in-place ROI fill ratios.

        Both denominators must be non-zero for meaningful measurements; Python
        raises ``ZeroDivisionError`` otherwise.
        """
        self.left = self.left / self.area  # Can only be 0 - 1
        self.right = self.right / self.area
        self.center = self.center / self.center_area


@export
@dataclass(slots=True)
class ParkingLot:
    """Detected parking lot in the camera frame.

    :ivar closer: Marker nearest the robot after ordering by image ``y``.
    :ivar further: Farther marker, or ``None`` if only one marker was detected.
    :ivar max_x: Frame width used to normalise marker coordinates.
    :ivar max_y: Frame height used to normalise marker coordinates.

    If the two mangenta parking lot restrictions contours are detected, the *closer* and *further* vision objects will be set accordingly.
    If only one restriction is visible from the current viewing angle, only *closer* will be set and *further* will be None.
    If no parking lot restrictions are detected, both *closer* and *further* will be None.
    """
    closer: VisionObject | None
    further: VisionObject | None
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        """Order markers and mutate their coordinates to frame-relative values.

        The closer marker has the larger image ``y`` coordinate. Bounding-box
        coordinates, centroids, and rotations are normalised in place by the
        supplied frame maxima; non-positive maxima map coordinates to ``0.0``.
        """
        if self.closer is not None and self.further is not None:
            # Image coordinates have origin at top-left, so larger y values are further down the image
            if self.closer.y_centroid < self.further.y_centroid:
                # Swap the two if they are in the wrong order
                self.closer, self.further = self.further, self.closer

        def _normalise(value: float, axis_max: float) -> float:
            """Scale one coordinate by its axis maximum, guarding zero."""
            if axis_max <= 0:
                return 0.0
            return float(value / axis_max)

        if self.closer is not None:
            self.closer.x_centroid = _normalise(
                self.closer.x_centroid, self.max_x)
            self.closer.y_centroid = _normalise(
                self.closer.y_centroid, self.max_y)
            self.closer.bbox = (
                _normalise(self.closer.bbox[0], self.max_x),
                _normalise(self.closer.bbox[1], self.max_y),
                _normalise(self.closer.bbox[2], self.max_x),
                _normalise(self.closer.bbox[3], self.max_y),
            )
        if self.further is not None:
            self.further.x_centroid = _normalise(
                self.further.x_centroid, self.max_x)
            self.further.y_centroid = _normalise(
                self.further.y_centroid, self.max_y)
            self.further.bbox = (
                _normalise(self.further.bbox[0], self.max_x),
                _normalise(self.further.bbox[1], self.max_y),
                _normalise(self.further.bbox[2], self.max_x),
                _normalise(self.further.bbox[3], self.max_y),
            )



@export
@dataclass(slots=True)
class WallsAndObstacles:
    """Normalised wall-distance and obstacle measurements.

    Wall values are ROI black-pixel fill ratios. Obstacles remain detected
    :class:`VisionObject` instances, while parking markers are normalised by
    :class:`ParkingLot`.

    :ivar walls: Normalised wall distances.
    :ivar obstacles: Detected obstacles, or ``None`` when no obstacle result is
        available for the frame.
    :ivar parking_lot: Detected parking markers and their normalisation bounds.
    """
    walls: Walls
    obstacles: Sequence[VisionObject] | None
    parking_lot: ParkingLot
