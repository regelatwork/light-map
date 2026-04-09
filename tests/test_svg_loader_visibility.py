from light_map.rendering.svg import SVGLoader
from light_map.visibility.visibility_types import VisibilityType


def create_test_svg(tmp_path, content):
    p = tmp_path / "test_visibility.svg"
    p.write_text(content)
    return str(p)


def test_get_visibility_blockers_empty(tmp_path):
    svg = create_test_svg(tmp_path, '<svg width="100" height="100"></svg>')
    loader = SVGLoader(svg)
    blockers = loader.get_visibility_blockers()
    assert len(blockers) == 0


def test_get_visibility_blockers_simple_wall(tmp_path):
    # Single path in a group named "Walls"
    svg_content = """<svg width="100" height="100">
      <g id="Walls">
        <path d="M 10 10 L 20 20" />
      </g>
    </svg>"""
    svg = create_test_svg(tmp_path, svg_content)
    loader = SVGLoader(svg)
    blockers = loader.get_visibility_blockers()

    assert len(blockers) == 1
    assert blockers[0].type == VisibilityType.WALL
    assert blockers[0].layer_name == "Walls"
    # (10, 10) to (20, 20)
    assert len(blockers[0].segments) == 2
    assert blockers[0].segments[0] == (10, 10)
    assert blockers[0].segments[1] == (20, 20)


def test_get_visibility_blockers_case_insensitive_substring(tmp_path):
    # Multiple layers with different naming styles
    svg_content = """<svg width="200" height="200">
      <g id="Secret-Door-1">
        <rect x="0" y="0" width="10" height="10" />
      </g>
      <g id="Main_Windows">
        <line x1="50" y1="50" x2="60" y2="60" />
      </g>
      <g id="Unbreakable_Window_Large">
        <circle cx="100" cy="100" r="10" />
      </g>
    </svg>"""
    svg = create_test_svg(tmp_path, svg_content)
    loader = SVGLoader(svg)
    blockers = loader.get_visibility_blockers()

    # We expect 3 blockers
    types = [b.type for b in blockers]
    assert VisibilityType.DOOR in types
    assert VisibilityType.WINDOW in types

    # Find the unbreakable window
    unbreakable = [b for b in blockers if b.is_unbreakable]
    assert len(unbreakable) == 1
    assert unbreakable[0].type == VisibilityType.WINDOW
    assert "unbreakable" in unbreakable[0].layer_name.lower()


def test_get_visibility_blockers_nested_transform(tmp_path):
    # Transform on the group and on the path
    svg_content = """<svg width="100" height="100">
      <g id="Wall-Layer" transform="translate(10, 10)">
        <path d="M 0 0 L 10 0" transform="scale(2, 1)" />
      </g>
    </svg>"""
    svg = create_test_svg(tmp_path, svg_content)
    loader = SVGLoader(svg)
    blockers = loader.get_visibility_blockers()

    assert len(blockers) == 1
    # Original (0,0)->(10,0)
    # Scaled (0,0)->(20,0)
    # Translated (10,10)->(30,10)
    assert blockers[0].segments[0] == (10, 10)
    assert blockers[0].segments[1] == (30, 10)


def test_get_visibility_blockers_reset_context(tmp_path):
    # Layer 1 is a wall, but it has a sibling that is not.
    # We want to make sure the state is scoped correctly.
    svg_content = """<svg width="200" height="200">
      <g id="Wall-Layer">
        <path d="M 0 0 L 10 10" />
      </g>
      <g id="Generic-Layer">
        <path d="M 50 50 L 60 60" />
      </g>
    </svg>"""
    svg = create_test_svg(tmp_path, svg_content)
    loader = SVGLoader(svg)
    blockers = loader.get_visibility_blockers()

    # Should only find the wall
    assert len(blockers) == 1
    assert blockers[0].layer_name == "Wall-Layer"
