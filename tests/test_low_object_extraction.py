import svgelements
from light_map.visibility.visibility_types import VisibilityType
from light_map.rendering.svg.blockers import get_visibility_blockers


def test_low_object_extraction_basic():
    """Verify that layers named 'Low Objects' extract LOW_OBJECT blockers."""
    svg = svgelements.SVG()
    layer = svgelements.Group()
    layer.values["inkscape:label"] = "Low Objects"

    # A rectangle (automatically closed)
    rect = svgelements.Rect(x=10, y=10, width=50, height=50)
    layer.append(rect)
    svg.append(layer)

    blockers = get_visibility_blockers(svg)

    assert len(blockers) == 1
    blocker = blockers[0]
    assert blocker.type == VisibilityType.LOW_OBJECT
    assert blocker.layer_name == "Low Objects"
    # Rect should be closed: start point == end point
    assert blocker.points[0] == blocker.points[-1]


def test_low_object_extraction_case_insensitive():
    """Verify case-insensitive and reordered naming: 'Object Low'."""
    svg = svgelements.SVG()
    layer = svgelements.Group()
    layer.values["inkscape:label"] = "OBJECT LOW"

    rect = svgelements.Rect(x=10, y=10, width=50, height=50)
    layer.append(rect)
    svg.append(layer)

    blockers = get_visibility_blockers(svg)

    assert len(blockers) == 1
    assert blockers[0].type == VisibilityType.LOW_OBJECT


def test_low_object_extraction_enforce_closed():
    """Verify that an open path in a Low Objects layer is forced closed."""
    svg = svgelements.SVG()
    layer = svgelements.Group()
    layer.values["inkscape:label"] = "Low Objects"

    # An open L-shape path: (0,0) -> (10,0) -> (10,10)
    path = svgelements.Path()
    path.append(svgelements.Move(0, 0))
    path.append(svgelements.Line((0, 0), (10, 0)))
    path.append(svgelements.Line((10, 0), (10, 10)))

    layer.append(path)
    svg.append(layer)

    blockers = get_visibility_blockers(svg)

    assert len(blockers) == 1
    blocker = blockers[0]
    assert blocker.type == VisibilityType.LOW_OBJECT

    # Should be closed: (0,0) -> (10,0) -> (10,10) -> (0,0)
    assert len(blocker.points) >= 3
    assert blocker.points[0] == (0.0, 0.0)
    assert blocker.points[-1] == (0.0, 0.0)
