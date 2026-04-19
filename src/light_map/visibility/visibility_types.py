from dataclasses import dataclass

# NOTE: Enums in this file are mirrored in frontend/src/types/system.ts
# Changes here MUST be kept in sync with the frontend.
# This is enforced by tests/test_enum_sync.py.
from enum import StrEnum
from typing import List, Tuple


class VisibilityType(StrEnum):
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"
    TALL_OBJECT = "tall_object"


@dataclass
class VisibilityBlocker:
    """
    Represents a physical or visual obstacle extracted from an SVG map.
    """

    points: List[Tuple[float, float]]  # Coordinate pairs (x, y)
    type: VisibilityType
    layer_name: str
    id: str = ""
    is_open: bool = False
    is_unbreakable: bool = False
