import pytest
from light_map.svg_loader import SVGLoader


@pytest.fixture
def grid_svg_file(tmp_path):
    svg_content = """<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <!-- Grid lines at 50px intervals -->
  <line x1="0" y1="50" x2="200" y2="50" stroke="black" />
  <line x1="0" y1="100" x2="200" y2="100" stroke="black" />
  <line x1="0" y1="150" x2="200" y2="150" stroke="black" />
  
  <line x1="50" y1="0" x2="50" y2="200" stroke="black" />
  <line x1="100" y1="0" x2="100" y2="200" stroke="black" />
  <line x1="150" y1="0" x2="150" y2="200" stroke="black" />
</svg>"""
    f = tmp_path / "test_grid.svg"
    f.write_text(svg_content)
    return str(f)


def test_detect_grid_spacing(grid_svg_file):
    loader = SVGLoader(grid_svg_file)
    spacing, origin_x, origin_y = loader.detect_grid_spacing()
    assert spacing == 50.0
    assert origin_x == 50.0
    assert origin_y == 50.0


def test_detect_grid_spacing_no_grid(tmp_path):
    svg_content = """<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect x="20" y="20" width="100" height="100" />
</svg>"""
    f = tmp_path / "no_grid.svg"
    f.write_text(svg_content)
    loader = SVGLoader(str(f))
    # A single rect gives 2 X coords (20, 120) and 2 Y coords (20, 120).
    # Unique X: 2. Unique Y: 2.
    # Requirements: len(unique) >= 3.
    # So it should return (0.0, 0.0, 0.0).
    spacing, origin_x, origin_y = loader.detect_grid_spacing()
    assert spacing == 0.0
    assert origin_x == 0.0
    assert origin_y == 0.0
