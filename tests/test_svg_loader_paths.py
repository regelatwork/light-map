import numpy as np
import pytest

from light_map.rendering.svg import SVGLoader


@pytest.fixture
def svg_discontinuous_path(tmp_path):
    # Two diagonal lines: (10,10)->(20,20) and (40,40)->(50,50)
    # They should NOT be connected.
    content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M 10,10 L 20,20 M 40,40 L 50,50" stroke="white" stroke-width="1" fill="none" />
    </svg>
    """
    p = tmp_path / "discontinuous.svg"
    p.write_text(content)
    return str(p)


def test_render_discontinuous_path(svg_discontinuous_path):
    loader = SVGLoader(svg_discontinuous_path)
    img = loader.render(100, 100)

    # Check that the lines are drawn
    # Point on first line (15, 15)
    assert np.any(img[15, 15] > 0), "First segment not drawn"

    # Point on second line (45, 45)
    assert np.any(img[45, 45] > 0), "Second segment not drawn"

    # Check that the gap is NOT drawn (30, 30)
    # If connected, (20,20) to (40,40) would pass through (30,30)
    assert np.all(img[30, 30] == 0), "Gap incorrectly connected"

    # Check that (25, 25) is also empty
    assert np.all(img[25, 25] == 0), "Gap incorrectly connected"
