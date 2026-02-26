import pytest
import numpy as np
from light_map.svg_loader import SVGLoader


@pytest.fixture
def svg_primitives(tmp_path):
    content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <!-- Rect -->
      <rect x="10" y="10" width="20" height="20" fill="none" stroke="white" stroke-width="1" />
      <!-- Circle -->
      <circle cx="50" cy="50" r="10" fill="none" stroke="white" stroke-width="1" />
      <!-- Polygon -->
      <polygon points="80,10 90,30 70,30" fill="none" stroke="white" stroke-width="1" />
      <!-- Line -->
      <line x1="10" y1="80" x2="30" y2="80" stroke="white" stroke-width="1" />
    </svg>
    """
    p = tmp_path / "primitives.svg"
    p.write_text(content)
    return str(p)


def test_render_primitives(svg_primitives):
    loader = SVGLoader(svg_primitives)
    img = loader.render(100, 100)

    # Rect check: top-left corner and bottom-right corner should be drawn
    assert np.any(img[10, 10] > 0) or np.any(img[10, 11] > 0), (
        "Rect not drawn at top-left"
    )
    assert np.any(img[30, 30] > 0) or np.any(img[29, 30] > 0), (
        "Rect not drawn at bottom-right"
    )

    # Circle check: top point (cx=50, cy=40) and bottom point (cx=50, cy=60)
    assert (
        np.any(img[40, 50] > 0) or np.any(img[40, 49] > 0) or np.any(img[40, 51] > 0)
    ), "Circle not drawn at top"
    assert (
        np.any(img[60, 50] > 0) or np.any(img[60, 49] > 0) or np.any(img[60, 51] > 0)
    ), "Circle not drawn at bottom"

    # Polygon check: top point (80,10)
    assert (
        np.any(img[10, 80] > 0) or np.any(img[10, 79] > 0) or np.any(img[10, 81] > 0)
    ), "Polygon not drawn at top point"

    # Line check: start (10,80) and end (30,80)
    assert np.any(img[80, 10] > 0) or np.any(img[80, 11] > 0), "Line not drawn at start"
    assert np.any(img[80, 30] > 0) or np.any(img[80, 29] > 0), "Line not drawn at end"
