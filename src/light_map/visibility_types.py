from dataclasses import dataclass
from enum import StrEnum
from typing import List, Tuple


class VisibilityType(StrEnum):
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"


@dataclass
class VisibilityBlocker:
    """
    Represents a physical or visual obstacle extracted from an SVG map.
    """

    segments: List[Tuple[float, float]]  # Flattened coordinates (x, y, x, y...)
    type: VisibilityType
    layer_name: str
    id: str = ""
    is_open: bool = False
    is_unbreakable: bool = False
