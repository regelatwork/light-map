import pytest
import base64
import cv2
import numpy as np
from light_map.svg import SVGLoader


@pytest.fixture
def grid_image_svg_file(tmp_path):
    # Create a grid image
    w, h = 200, 200
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img.fill(255)  # White background

    # Draw black grid lines at 50px intervals
    step = 50
    for x in range(0, w, step):
        cv2.line(img, (x, 0), (x, h), (0, 0, 0), 2)
    for y in range(0, h, step):
        cv2.line(img, (0, y), (w, y), (0, 0, 0), 2)

    # Convert to base64
    _, buffer = cv2.imencode(".png", img)
    b64_str = base64.b64encode(buffer).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64_str}"

    svg_content = f"""<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <image href="{data_uri}" x="0" y="0" width="200" height="200" />
</svg>"""

    f = tmp_path / "test_grid_raster.svg"
    f.write_text(svg_content)
    return str(f)


def test_detect_grid_spacing_raster(grid_image_svg_file):
    loader = SVGLoader(grid_image_svg_file)
    # The image has 50px grid.
    # SVG is 200x200.
    # The logic should detect approx 50.0.
    spacing, origin_x, origin_y = loader.detect_grid_spacing()

    # Allow some tolerance for raster analysis (e.g. +/- 5 pixels)
    print(f"Detected: {spacing}")
    assert 45.0 <= spacing <= 55.0
    assert origin_x == 0.0
    assert origin_y == 0.0
