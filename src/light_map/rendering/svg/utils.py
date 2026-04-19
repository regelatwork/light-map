import svgelements
import math
from typing import Any, Optional, Tuple
from light_map.visibility.visibility_types import VisibilityType


def get_element_label(element: Any) -> Optional[str]:
    """Extracts the label or ID from an SVG element."""
    keys = [
        "inkscape:label",
        "{http://www.inkscape.org/namespaces/inkscape}label",
        "id",
    ]
    for key in keys:
        if key in element.values:
            return str(element.values[key])
    if hasattr(element, "id") and element.id:
        return str(element.id)
    return None


def get_element_opacity(element: Any) -> float:
    """Extracts overall element opacity."""
    if "opacity" in element.values:
        try:
            return float(element.values["opacity"])
        except ValueError:
            pass
    return 1.0


def get_viewport_matrix(
    target_width: int,
    target_height: int,
    scale_factor: float,
    offset_x: int,
    offset_y: int,
    rotation: float,
    quality: float,
) -> svgelements.Matrix:
    """Calculates the final viewport matrix including quality scaling."""
    cx, cy = target_width / 2, target_height / 2
    vp_matrix = svgelements.Matrix()
    vp_matrix.post_scale(scale_factor, scale_factor)
    vp_matrix.post_rotate(math.radians(rotation), cx, cy)
    vp_matrix.post_translate(offset_x, offset_y)

    q_matrix = svgelements.Matrix()
    q_matrix.post_scale(quality, quality)
    return vp_matrix * q_matrix


def get_visibility_type(label: str) -> Tuple[Optional[VisibilityType], bool]:
    """Maps an element label to a VisibilityType and unbreakable status."""
    id_lower = label.lower()
    if "wall" in id_lower:
        return VisibilityType.WALL, False
    if "door" in id_lower:
        return VisibilityType.DOOR, False
    if "window" in id_lower:
        return VisibilityType.WINDOW, "unbreakable" in id_lower
    if "tall" in id_lower and "object" in id_lower:
        return VisibilityType.TALL_OBJECT, False
    return None, False
