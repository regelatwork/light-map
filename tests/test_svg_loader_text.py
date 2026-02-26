import pytest
import numpy as np
from light_map.svg_loader import SVGLoader


@pytest.fixture
def svg_with_text(tmp_path):
    # SVG with text
    content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <text x="10" y="50" font-family="Arial" font-size="20" fill="white">Hello</text>
    </svg>
    """
    p = tmp_path / "text.svg"
    p.write_text(content)
    return str(p)


def test_render_text(svg_with_text):
    loader = SVGLoader(svg_with_text)
    img = loader.render(100, 100)

    # Check for white pixels (BGR: 255, 255, 255)
    # If text is not rendered, image will be all black.
    assert np.count_nonzero(img) > 0


def test_render_colored_text(tmp_path):
    content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <text x="10" y="50" font-size="20" fill="red">Error</text>
    </svg>
    """
    p = tmp_path / "colored_text.svg"
    p.write_text(content)

    loader = SVGLoader(str(p))
    img = loader.render(100, 100)

    # Check for red pixels (BGR: 0, 0, 255)
    assert np.count_nonzero(img) > 0
    # Red channel should be high
    assert np.max(img[:, :, 2]) > 200
    # Blue and Green should be low for "red"
    assert np.max(img[:, :, 0]) < 50
    assert np.max(img[:, :, 1]) < 50
