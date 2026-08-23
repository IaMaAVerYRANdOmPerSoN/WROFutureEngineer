"""Vision data structures.

Defines :class:`VisionObject` for detected contours and :class:`Walls`
for normalised wall-distance measurements.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from ..lib import export



def get_pose(contour: np.ndarray) -> tuple[float, float, float]:
    """Calculate the centroid of a contour.

    :param contour: OpenCV contour (Nx1x2 array of points).
    :return: Centroid coordinates (x, y).
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
    :ivar bbox: Bounding rectangle ``(x, y, w, h)``.
    :ivar x_centroid: X coordinate of the bounding-box centre.
    :ivar y_centroid: Y coordinate of the bounding-box centre.
    :ivar rotation: Normalised rotation angle of the contour (-1 to 1).
    """
    contour: np.ndarray
    color: str
    bbox: cv2.typing.Rect = None # pyright: ignore[reportAssignmentType]
    x_centroid: float = None # pyright: ignore[reportAssignmentType]
    y_centroid: float = None # pyright: ignore[reportAssignmentType]
    rotation: float = None # pyright: ignore[reportAssignmentType]

    def __post_init__(self) -> None:
        """Compute bounding-box and centroid properties after dataclass init."""
        # Added custom type stub, default type stubs use Sequence[int]
        self.bbox: cv2.typing.Rect = cv2.boundingRect(self.contour)
        self.x_centroid, self.y_centroid, self.rotation = get_pose(self.contour)
        self.x_centroid = float(self.x_centroid)
        self.y_centroid = float(self.y_centroid)
        self.rotation = float(np.clip(self.rotation / 90.0, -1.0, 1.0))


@export
@dataclass(slots=True)
class OpenChallengeWalls:
    """Normalised wall-distance measurements.

    Distances are expressed as the fraction of black pixels in the
    left and right regions of interest, divided by ROI area.

    :ivar left: Normalised distance to the left wall (0-1).
    :ivar right: Normalised distance to the right wall (0-1).
    :ivar area: Total pixel area of the ROI used for normalisation.
    """
    left: float
    right: float
    center: float
    area: float
    center_area: float

    def __post_init__(self) -> None:
        """Normalise wall distances by dividing by ROI area."""
        self.left = self.left / self.area  # Can only be 0 - 1
        self.right = self.right / self.area
        self.center = self.center / self.center_area


@export
@dataclass(slots=True)
class ObstacleChallengeWalls:
    """Normalised wall-distance measurements for the Obstacle Challenge.

    Distances are expressed as the distance between the bounding box of the wall contour and the center of the frame, divided by the maximum possible distance (half the frame width).
    (This is a different metric than the Open Challenge, which uses pixel counts.)

    The :class:`ObstacleChallengeWalls` dataclass also bundles raw contours for further processing, such as calculating the midpoint to an obstacle.

    :ivar left: Normalised distance to the left wall (0-1).
    :ivar right: Normalised distance to the right wall (0-1).
    :ivar area: Total pixel area of the ROI used for normalisation.
    """
    left: float
    right: float
    center: float
    max_distance: float
    center_area: float
    left_raw: VisionObject | None
    right_raw: VisionObject | None

    def __post_init__(self) -> None:
        """Normalise wall distances by dividing by ROI area."""
        self.left = float(self.left / self.max_distance)  # Can only be 0 - 1
        self.right = float(self.right / self.max_distance)
        self.center = float(self.center / self.center_area)


@export
@dataclass(slots=True)
class ParkingLot:
    """Detected parking lot in the camera frame.

    :ivar closer: The closer vision object representing nearest edge of the parking lot.
    :ivar further: The further vision object representing the far edge of the parking lot.

    If the two mangenta parking lot restrictions contours are detected, the *closer* and *further* vision objects will be set accordingly.
    If only one restriction is visible from the current viewing angle, only *closer* will be set and *further* will be None.
    If no parking lot restrictions are detected, both *closer* and *further* will be None.
    """
    closer: VisionObject | None
    further: VisionObject | None
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        """Ensure that the closer and further vision objects are correctly assigned based on their y-centroid values, then normalise."""
        if self.closer is not None and self.further is not None:
            if self.closer.y_centroid < self.further.y_centroid: # Image coordinates have origin at top-left, so larger y values are further down the image
                # Swap the two if they are in the wrong order
                self.closer, self.further = self.further, self.closer

        def _normalise(value: float, axis_max: float) -> float:
            """Scale one coordinate by its axis maximum, guarding zero."""
            if axis_max <= 0:
                return 0.0
            return float(value / axis_max)

        if self.closer is not None:
            self.closer.x_centroid = _normalise(self.closer.x_centroid, self.max_x)
            self.closer.y_centroid = _normalise(self.closer.y_centroid, self.max_y)
        if self.further is not None:
            self.further.x_centroid = _normalise(self.further.x_centroid, self.max_x)
            self.further.y_centroid = _normalise(self.further.y_centroid, self.max_y)


@export
@dataclass(slots=True)
class WallsAndObstacles:
    """Normalised wall-distance and obstacle measurements.

    Wall distances are expressed as the distance between the centroid of the wall contour and the center of the frame,
    while obstacles are expressed as visionObjects in the camera frame.

    :ivar walls: Normalised wall distances.
    :ivar obstacles: Normalised obstacle distances.
    """
    walls: ObstacleChallengeWalls
    obstacles: Sequence[VisionObject] | None
    parking_lot: ParkingLot
