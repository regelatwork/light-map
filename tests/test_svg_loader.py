import pytest
import numpy as np
from light_map.svg_loader import SVGLoader


@pytest.fixture
def sample_svg_file(tmp_path):
    svg_content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="10" width="80" height="80" stroke="red" stroke-width="2" fill="none" />
      <line x1="0" y1="0" x2="100" y2="100" stroke="blue" stroke-width="1" />
    </svg>
    """
    p = tmp_path / "test.svg"
    p.write_text(svg_content)
    return str(p)


def test_loader_initialization_valid(sample_svg_file):
    loader = SVGLoader(sample_svg_file)
    assert loader.svg is not None
    # svgelements parses objects. We can check if it found elements.
    elements = list(loader.svg.elements())
    assert len(elements) > 0


def test_loader_initialization_invalid():
    loader = SVGLoader("non_existent.svg")
    # Should handle gracefully, maybe log error but not crash __init__?
    # Based on implementation: prints error and sets svg=None
    assert loader.svg is None


def test_render_dimensions(sample_svg_file):
    loader = SVGLoader(sample_svg_file)
    width, height = 200, 150
    image = loader.render(width, height)

    assert image is not None
    assert image.shape == (height, width, 3)
    assert image.dtype == np.uint8


def test_render_content(sample_svg_file):
    loader = SVGLoader(sample_svg_file)
    width, height = 100, 100

    # Render 1:1
    img_base = loader.render(width, height, scale_factor=1.0)

    # Check if we have non-black pixels (content rendered)
    assert np.sum(img_base) > 0

    # Check colors roughly
    # Red rect stroke: BGR (0, 0, 255)
    # Blue line stroke: BGR (255, 0, 0)

    # We expect some red pixels
    red_mask = (img_base[:, :, 2] > 0) & (img_base[:, :, 0] == 0)
    assert np.any(red_mask), "Should contain red pixels from rect"

    # We expect some blue pixels
    blue_mask = (img_base[:, :, 0] > 0) & (img_base[:, :, 2] == 0)
    assert np.any(blue_mask), "Should contain blue pixels from line"


def test_render_transformations(sample_svg_file):
    loader = SVGLoader(sample_svg_file)
    width, height = 100, 100

    # 1. Base Render
    img_base = loader.render(width, height, scale_factor=1.0)
    base_pixels = np.count_nonzero(img_base)

    # 2. Scale Up (2.0) -> Lines should be thicker/longer
    img_scaled = loader.render(width, height, scale_factor=2.0)
    scaled_pixels = np.count_nonzero(img_scaled)

    assert scaled_pixels > base_pixels, (
        "Scaled up image should have more colored pixels (thicker lines)"
    )

    # 3. Translate (Offset) -> Content shifts
    # Shift by 1000px (offscreen)
    img_shifted = loader.render(width, height, offset_x=1000, offset_y=1000)
    shifted_pixels = np.count_nonzero(img_shifted)

    assert shifted_pixels == 0, "Image shifted offscreen should be empty"
