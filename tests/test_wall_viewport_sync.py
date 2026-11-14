import numpy as np
import pytest

from light_map.rendering.svg.loader import SVGLoader
from light_map.visibility.visibility_types import VisibilityType


@pytest.fixture
def svg_with_wall_and_door(tmp_path):
    svg_content = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" id="layer_walls" inkscape:label="Walls">
    <path
       style="fill:none;stroke:#ffffff;stroke-width:2"
       d="M 20,20 L 80,20"
       id="wall_path_1" />
  </g>
</svg>
"""
    svg_file = tmp_path / "wall_sync_test.svg"
    svg_file.write_text(svg_content)
    return str(svg_file)


def test_wall_rendering_does_not_mutate_svg_across_pans(svg_with_wall_and_door):
    """
    Rendering an SVG multiple times with different viewport offsets/scales
    must not mutate the underlying SVG path segments in place.
    """
    loader = SVGLoader(svg_with_wall_and_door)

    blockers_before = loader.get_visibility_blockers()
    walls_before = [b for b in blockers_before if b.type == VisibilityType.WALL]
    assert len(walls_before) == 1
    assert walls_before[0].points == [(20.0, 20.0), (80.0, 20.0)]

    # Render 1: Pan to (+10, +10) at scale 1.0
    # Wall (20,20)->(80,20) should appear at y=30, x=30..90
    img1 = loader.render(200, 200, scale_factor=1.0, offset_x=10, offset_y=10)
    assert np.any(img1[30, 50] > 0), "Wall should be rendered at y=30, x=50 in first render"

    # Render 2: Pan to (+40, +50) at scale 1.0
    # Wall (20,20)->(80,20) should appear at y=70, x=60..120
    img2 = loader.render(200, 200, scale_factor=1.0, offset_x=40, offset_y=50)
    assert np.any(img2[70, 90] > 0), "Wall should be rendered at y=70, x=90 in second render"
    assert not np.any(img2[30, 50] > 0), "Wall should no longer be at old position y=30"

    # Blockers extracted after rendering must remain in original SVG coordinates
    blockers_after = loader.get_visibility_blockers()
    walls_after = [b for b in blockers_after if b.type == VisibilityType.WALL]
    assert walls_after[0].points == [(20.0, 20.0), (80.0, 20.0)]
