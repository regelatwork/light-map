import svgelements
from typing import List, Tuple, Dict, Optional
from ..visibility_types import VisibilityType, VisibilityBlocker
from .utils import get_element_label, get_visibility_type
from .geometry import sample_segment


def extract_visibility_blocker(
    element: svgelements.Shape,
    v_type: VisibilityType,
    layer_name: str,
    is_unbreakable: bool,
    id_counts: Dict[str, int],
) -> Optional[VisibilityBlocker]:
    """Extracts a VisibilityBlocker from a shape element."""
    element_id = get_element_label(element)

    if not element_id or element_id == layer_name:
        count = id_counts.get(layer_name, 0) + 1
        id_counts[layer_name] = count
        final_id = f"{layer_name}_{count}"
    else:
        final_id = element_id

    path = svgelements.Path(element)
    segments: List[Tuple[float, float]] = []
    for segment in path:
        if isinstance(segment, svgelements.Move):
            continue
        if not segments:
            segments.append((segment.start.x, segment.start.y))

        if isinstance(segment, svgelements.Line):
            segments.append((segment.end.x, segment.end.y))
        elif isinstance(
            segment,
            (svgelements.QuadraticBezier, svgelements.CubicBezier, svgelements.Arc),
        ):
            segments.extend(sample_segment(segment, points_per_unit=0.5))
        elif isinstance(segment, svgelements.Close) and segments:
            segments.append((segment.end.x, segment.end.y))

    return (
        VisibilityBlocker(
            id=final_id,
            segments=segments,
            type=v_type,
            layer_name=layer_name,
            is_unbreakable=is_unbreakable,
        )
        if segments
        else None
    )


def get_visibility_blockers(svg: svgelements.SVG) -> List[VisibilityBlocker]:
    """Extracts walls, doors, and windows from the SVG based on layer names."""
    if not svg:
        return []

    blockers, id_counts = [], {}

    def traverse(element, v_type=None, layer_name="", is_unbreakable=False):
        label = get_element_label(element)
        if label:
            new_type, new_unbreakable = get_visibility_type(label)
            if new_type:
                v_type, layer_name, is_unbreakable = new_type, label, new_unbreakable

        if isinstance(element, svgelements.Shape) and v_type:
            blocker = extract_visibility_blocker(
                element, v_type, layer_name, is_unbreakable, id_counts
            )
            if blocker:
                blockers.append(blocker)

        if isinstance(element, (svgelements.Group, svgelements.SVG)):
            for child in element:
                traverse(child, v_type, layer_name, is_unbreakable)

    traverse(svg)
    return blockers
