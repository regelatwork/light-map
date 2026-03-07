import pytest
import numpy as np
from light_map.svg_loader import SVGLoader
from light_map.visibility_types import VisibilityType


@pytest.fixture
def svg_symbols(tmp_path):
    content = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <symbol id="pillar">
          <circle cx="0" cy="0" r="5" fill="white" />
        </symbol>
      </defs>
      
      <!-- Walls group -->
      <g id="walls">
        <use href="#pillar" x="20" y="20" />
        <use href="#pillar" x="80" y="20" />
      </g>
      
      <!-- This circle should NOT be rendered as a wall because it's in defs -->
      <defs>
        <g id="hidden_walls">
           <rect id="ghost" x="50" y="50" width="10" height="10" />
        </g>
      </defs>
    </svg>
    """
    p = tmp_path / "symbols.svg"
    p.write_text(content)
    return str(p)


def test_symbol_rendering(svg_symbols):
    loader = SVGLoader(svg_symbols)
    img = loader.render(100, 100)

    # Pillar 1 at (20, 20)
    assert np.any(img[20, 20] > 0)
    # Pillar 2 at (80, 20)
    assert np.any(img[20, 80] > 0)

    # Ghost rect at (50, 50) should NOT be there
    assert not np.any(img[50:60, 50:60] > 0)


def test_symbol_visibility_blockers(svg_symbols):
    loader = SVGLoader(svg_symbols)
    blockers = loader.get_visibility_blockers()

    # We expect 2 blockers (the two used pillars)
    # The 'ghost' rect should be ignored.

    wall_blockers = [b for b in blockers if b.type == VisibilityType.WALL]
    print(f"Blockers found: {[b.id for b in wall_blockers]}")

    # Currently it might find 3 (definition + 2 uses) or 0 (if Use not traversed)
    assert len(wall_blockers) == 2

    # Check positions
    # Pillar segments should be around (20, 20) and (80, 20)
    p1 = next(b for b in wall_blockers if b.segments[0][0] < 50)
    p2 = next(b for b in wall_blockers if b.segments[0][0] > 50)

    assert abs(p1.segments[0][0] - 25) < 10  # r=5 at x=20 -> x ranges 15-25
    assert abs(p2.segments[0][0] - 85) < 10
