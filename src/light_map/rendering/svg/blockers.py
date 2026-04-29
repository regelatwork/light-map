
import svgelements

from light_map.rendering.svg.geometry import sample_segment
from light_map.rendering.svg.utils import get_element_label, get_visibility_type
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


def extract_visibility_blocker(
    element: svgelements.Shape,
    v_type: VisibilityType,
    layer_name: str,
    is_unbreakable: bool,
    id_counts: dict[str, int],
) -> VisibilityBlocker | None:
    """Extracts a VisibilityBlocker from a shape element."""
    element_id = get_element_label(element)

    if not element_id or element_id == layer_name:
        count = id_counts.get(layer_name, 0) + 1
        id_counts[layer_name] = count
        final_id = f"{layer_name}_{count}"
    else:
        final_id = element_id

    path = svgelements.Path(element)
    points: list[tuple[float, float]] = []
    for segment in path:
        if isinstance(segment, svgelements.Move):
            continue
        if not points:
            points.append((segment.start.x, segment.start.y))

        if isinstance(segment, svgelements.Line):
            points.append((segment.end.x, segment.end.y))
        elif isinstance(
            segment,
            (svgelements.QuadraticBezier, svgelements.CubicBezier, svgelements.Arc),
        ):
            points.extend(sample_segment(segment, points_per_unit=0.5))
        elif isinstance(segment, svgelements.Close) and points:
            points.append((segment.end.x, segment.end.y))

    if v_type in (VisibilityType.TALL_OBJECT, VisibilityType.LOW_OBJECT) and points:
        if points[0] != points[-1]:
            points.append(points[0])

    return (
        VisibilityBlocker(
            id=final_id,
            points=points,
            type=v_type,
            layer_name=layer_name,
            is_unbreakable=is_unbreakable,
        )
        if points
        else None
    )


def get_visibility_blockers(svg: svgelements.SVG) -> list[VisibilityBlocker]:
    """Extracts walls, doors, and windows from the SVG based on layer names."""
    if not svg:
        return []

    blockers, id_counts = [], {}

    def traverse(element, v_type=None, layer_name="", is_unbreakable=False):
        tag = element.values.get("tag")
        if tag in ("symbol", "defs"):
            return

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

        # Recurse into containers (Groups, SVG, and Use elements)
        if isinstance(element, list):
            for child in element:
                traverse(child, v_type, layer_name, is_unbreakable)

    traverse(svg)
    return blockers
