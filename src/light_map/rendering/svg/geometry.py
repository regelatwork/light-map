from collections import Counter
from typing import Any

import numpy as np
import svgelements


def sample_segment(
    segment: Any, points_per_unit: float = 1.0
) -> list[tuple[float, float]]:
    """Samples a curve segment adaptively based on its length."""
    if isinstance(segment, svgelements.Line):
        return [(segment.end.x, segment.end.y)]

    try:
        length = segment.length()
    except (AttributeError, Exception):
        length = 10.0

    num_steps = max(4, min(100, int(length * points_per_unit)))
    points = []
    for i in range(1, num_steps + 1):
        t = i / float(num_steps)
        p = segment.point(t)
        points.append((p.x, p.y))
    return points


def process_segment(
    segment: Any,
    ppu: float,
    current_points: list[tuple[int, int]],
) -> bool:
    """Processes a single segment and adds points to current_points. Returns True if segment was a Close."""
    if isinstance(segment, svgelements.Line):
        current_points.append((int(segment.end.x), int(segment.end.y)))
    elif isinstance(segment, svgelements.Close):
        return True
    elif isinstance(
        segment, (svgelements.QuadraticBezier, svgelements.CubicBezier, svgelements.Arc)
    ):
        points = sample_segment(segment, points_per_unit=ppu)
        for px, py in points:
            current_points.append((int(px), int(py)))
    return False


def convert_path_to_points(
    transformed_path: svgelements.Path,
    element_naturally_closed: bool,
    ppu: float,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Converts an SVG path to a list of OpenCV-compatible point arrays."""
    closed_subpaths, open_subpaths = [], []
    current_points, is_current_closed = [], False

    for segment in transformed_path:
        if isinstance(segment, svgelements.Move):
            if current_points:
                subpath_array = np.array(current_points, dtype=np.int32).reshape(
                    (-1, 1, 2)
                )
                if is_current_closed or element_naturally_closed:
                    closed_subpaths.append(subpath_array)
                else:
                    open_subpaths.append(subpath_array)
                current_points = []
            is_current_closed = False
            continue

        if not current_points:
            current_points.append((int(segment.start.x), int(segment.start.y)))
        is_current_closed = process_segment(segment, ppu, current_points)

    if current_points:
        subpath_array = np.array(current_points, dtype=np.int32).reshape((-1, 1, 2))
        if is_current_closed or element_naturally_closed:
            closed_subpaths.append(subpath_array)
        else:
            open_subpaths.append(subpath_array)
    return closed_subpaths, open_subpaths


def collect_path_grid_coords(
    element: svgelements.Path, x_coords: list[float], y_coords: list[float]
):
    """Collects grid lines from path segments."""
    for segment in element:
        if isinstance(segment, svgelements.Line):
            p1, p2 = segment.start, segment.end
            if abs(p1.x - p2.x) < 0.1 and abs(p1.y - p2.y) > 10:
                x_coords.append(p1.x)
            elif abs(p1.y - p2.y) < 0.1 and abs(p1.x - p2.x) > 10:
                y_coords.append(p1.y)


def collect_line_grid_coords(
    element: Any, x_coords: list[float], y_coords: list[float]
):
    """Collects grid lines from line elements."""
    if hasattr(element, "x1"):
        p1x, p1y, p2x, p2y = element.x1, element.y1, element.x2, element.y2
    else:
        p1x, p1y, p2x, p2y = (
            element.start.x,
            element.start.y,
            element.end.x,
            element.end.y,
        )
    if abs(p1x - p2x) < 0.1:
        x_coords.append(p1x)
    elif abs(p1y - p2y) < 0.1:
        y_coords.append(p1y)


def collect_grid_coordinates(svg: svgelements.SVG) -> tuple[list[float], list[float]]:
    """Collects candidate grid coordinates from SVG elements."""
    x_coords = []
    y_coords = []
    for element in svg.elements():
        if isinstance(element, svgelements.Path):
            collect_path_grid_coords(element, x_coords, y_coords)
        elif isinstance(element, svgelements.Rect):
            x_coords.extend([element.x, element.x + element.width])
            y_coords.extend([element.y, element.y + element.height])
        elif isinstance(element, (svgelements.Line, svgelements.SimpleLine)):
            collect_line_grid_coords(element, x_coords, y_coords)
    return x_coords, y_coords


def analyze_spacing_and_origin(coords: list[float]) -> tuple[float, float]:
    """Heuristic to find the most likely grid spacing and origin from coordinates."""
    if not coords:
        return 0.0, 0.0
    sorted_coords = sorted([round(c, 1) for c in coords])
    unique_coords = sorted(list(set(sorted_coords)))
    if len(unique_coords) < 3:
        return 0.0, 0.0
    gaps = []
    for i in range(len(unique_coords) - 1):
        gap = unique_coords[i + 1] - unique_coords[i]
        if gap > 1.0:
            gaps.append(round(gap, 1))
    if not gaps:
        return 0.0, 0.0
    counts = Counter(gaps)
    most_common = counts.most_common(1)
    if not most_common or most_common[0][1] < 2:
        return 0.0, 0.0
    return most_common[0][0], unique_coords[0]
