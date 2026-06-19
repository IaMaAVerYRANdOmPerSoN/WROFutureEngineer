"""Vision data structures.

Defines :class:`VisionObject` for detected contours and :class:`Walls`
for normalised wall-distance measurements.
"""

from dataclasses import dataclass
from ..lib import export
import numpy as np
import cv2
from typing import Tuple


@export
@dataclass
class VisionObject:
    """A detected object in the camera frame.

    Wraps an OpenCV contour with colour metadata and derived properties
    (bounding box, centroid coordinates).

    :ivar contour: OpenCV contour (Nx1x2 array of points).
    :ivar color: Colour label string (e.g. ``"green"``, ``"red"``).
    :ivar bbox: Bounding rectangle ``(x, y, w, h)``.
    :ivar x_centroid: X coordinate of the bounding-box centre.
    :ivar y_centroid: Y coordinate of the bounding-box centre.
    """
    contour: np.ndarray
    color: str

    def __post_init__(self):
        """Compute bounding-box and centroid properties after dataclass init."""
        # Added custom type stub, default type stubs use Sequence[int]
        self.bbox: cv2.typing.Rect = cv2.boundingRect(self.contour)
        x, y, w, h = self.bbox
        self.x_centroid: float = x + w/2
        self.y_centroid: float = y + h/2
        # Bottom y deprecated because perspective transform makes everything top-down


@export
@dataclass
class Walls:
    """Normalised wall-distance measurements.

    Distances are expressed as the fraction of black pixels in the
    left and right regions of interest, divided by ROI area.

    :ivar left: Normalised distance to the left wall (0–1).
    :ivar right: Normalised distance to the right wall (0–1).
    :ivar area: Total pixel area of the ROI used for normalisation.
    """
    left: float
    right: float
    area: float

    def __post_init__(self):
        """Normalise wall distances by dividing by ROI area."""
        self.left = self.left / self.area # Can only be 0 - 1
        self.right = self.right / self.area