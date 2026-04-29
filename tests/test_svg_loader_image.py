import base64
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from light_map.rendering.svg import SVGLoader


@pytest.fixture
def svg_with_fill(tmp_path):
    # A green filled rect
    content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="10" width="80" height="80" fill="green" stroke="none" />
    </svg>
    """
    p = tmp_path / "fill.svg"
    p.write_text(content)
    return str(p)


@pytest.fixture
def svg_with_image(tmp_path):
    # Create a small red PNG in memory
    img = Image.new("RGB", (10, 10), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # SVG embedding the image
    content = f"""
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
      <image x="10" y="10" width="80" height="80" xlink:href="data:image/png;base64,{b64}" />
    </svg>
    """
    p = tmp_path / "image.svg"
    p.write_text(content)
    return str(p)


def test_render_filled_shape(svg_with_fill):
    loader = SVGLoader(svg_with_fill)
    img = loader.render(100, 100)

    # Check for green pixels (BGR: 0, 128, 0) - "green" in SVG is usually #008000 (0, 128, 0)
    # or strict SVG color mapping.

    # Just check non-zero
    assert np.count_nonzero(img) > 0

    # Check center pixel
    # OpenCV uses BGR. Green is (0, G, 0).
    center_px = img[50, 50]
    assert center_px[1] > 0  # Green channel
    assert center_px[0] == 0  # Blue
    assert center_px[2] == 0  # Red


def test_render_embedded_image(svg_with_image):
    loader = SVGLoader(svg_with_image)
    img = loader.render(100, 100)

    # Check for red pixels (BGR: 0, 0, 255)
    assert np.count_nonzero(img) > 0

    center_px = img[50, 50]
    assert center_px[2] > 0  # Red channel
    assert center_px[0] == 0  # Blue
    assert center_px[1] == 0  # Green
