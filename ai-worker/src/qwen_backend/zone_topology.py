"""Current EyesOnU jurisdiction topology contract.

The first deployment scenario is fixed at four zones with four camera
positions per zone.  Keeping the contract in one module prevents the API,
probability model, and routing policy from silently drifting apart when the
layout is changed.
"""

from typing import Final

JURISDICTION_ZONE_COUNT: Final = 4
CAMERAS_PER_ZONE: Final = 4
CAMERA_POSITIONS: Final[frozenset[int]] = frozenset(
    range(1, CAMERAS_PER_ZONE + 1)
)
DEFAULT_ZONE_ADJACENCY: Final[tuple[tuple[int, int], ...]] = (
    (1, 2),
    (1, 3),
    (2, 4),
    (3, 4),
)

