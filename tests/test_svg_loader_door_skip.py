import pytest
import numpy as np
from light_map.svg_loader import SVGLoader


@pytest.fixture
def svg_with_door(tmp_path):
    # SVG with a red wall and a blue door
    svg_content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <g id="walls">
        <line x1="10" y1="10" x2="90" y2="10" stroke="red" stroke-width="2" />
      </g>
      <g id="doors">
        <line x1="10" y1="20" x2="90" y2="20" stroke="blue" stroke-width="2" />
      </g>
    </svg>
    """
    p = tmp_path / "door_test.svg"
    p.write_text(svg_content)
    return str(p)


def test_render_skips_doors(svg_with_door):
    loader = SVGLoader(svg_with_door)
    width, height = 100, 100
    image = loader.render(width, height, scale_factor=1.0)

    # Wall is red (BGR: 0, 0, 255)
    red_mask = (image[:, :, 2] > 200) & (image[:, :, 0] < 50)
    assert np.any(red_mask), "Wall should be rendered (red)"

    # Door is blue (BGR: 255, 0, 0)
    # It SHOULD be skipped
    blue_mask = (image[:, :, 0] > 200) & (image[:, :, 2] < 50)
    assert not np.any(blue_mask), "Door should NOT be rendered (blue)"


def test_render_skips_doors_inkscape(tmp_path):
    # Test skipping using inkscape:label
    svg_content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
      <g inkscape:label="The Doors" id="g1">
        <line x1="10" y1="20" x2="90" y2="20" stroke="blue" stroke-width="2" />
      </g>
    </svg>
    """
    p = tmp_path / "door_inkscape.svg"
    p.write_text(svg_content)

    loader = SVGLoader(str(p))
    image = loader.render(100, 100, scale_factor=1.0)

    blue_mask = (image[:, :, 0] > 200) & (image[:, :, 2] < 50)
    assert not np.any(blue_mask), "Door with inkscape:label should NOT be rendered"
