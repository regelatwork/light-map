from unittest.mock import Mock

import pytest

from light_map.core.common_types import GridType, MapRenderState, SelectionState, ViewportState
from light_map.state.world_state import WorldState


class MockToken:
    def __init__(self, id: int, name: str, type: str):
        self.id = id
        self.name = name
        self.type = type
        self.world_x = 0.0
        self.world_y = 0.0
        self.world_z = 0.0
        self.marker_x = None
        self.marker_y = None
        self.marker_z = 0.0
        self.grid_x = None
        self.grid_y = None
        self.screen_x = None
        self.screen_y = None
        self.confidence = 1.0
        self.is_occluded = False
        self.is_duplicate = False
        self.color = None
        self.profile = None
        self.size = None
        self.height_mm = None


class MockResult:
    def __init__(self, ac_bonus: int, reflex_bonus: int, explanation: str):
        self.ac_bonus = ac_bonus
        self.reflex_bonus = reflex_bonus
        self.explanation = explanation


@pytest.fixture
def mock_world_state():
    world = WorldState()

    # Mock the viewport property so it returns a mock object with a to_dict method
    world.viewport = Mock(spec=ViewportState)
    world.viewport.to_dict.return_value = {}

    world.menu_state = None

    world.tokens = [
        MockToken(1, "Target 1", "NPC"),
        MockToken(2, "Hero 1", "PC"),
    ]

    world.tactical_bonuses = {
        1: MockResult(2, 1, "Cover"),
        2: MockResult(1, 2, "None"),
    }

    world.selection = SelectionState(type="TOKEN", id="2")

    world.map_render_state = Mock(spec=MapRenderState)

    world.dwell_state = {}
    world.summon_progress = 0.0
    world.inspected_token_id = None
    world.grid_spacing_svg = 1.0
    world.grid_origin_svg_x = 0.0
    world.grid_origin_svg_y = 0.0

    world.grid_type = GridType.SQUARE
    world.grid_overlay_visible = True
    world.grid_overlay_color = "white"

    world.current_scene_name = "MapScene"

    return world


def test_world_state_to_dict_tactical_types(mock_world_state):
    data = mock_world_state.to_dict()
    targets = data["tactical"]["targets"]

    # Check target_1
    target_1 = next((t for t in targets if t["id"] == 1), None)
    assert target_1 is not None
    assert target_1["type"] == "NPC"

    # Check hero_1
    hero_1 = next((t for t in targets if t["id"] == 2), None)
    assert hero_1 is not None
    assert hero_1["type"] == "PC"

    # Check a missing target (should default to NPC)
    mock_world_state.tactical_bonuses[99] = MockResult(1, 1, "None")
    data = mock_world_state.to_dict()
    targets = data["tactical"]["targets"]

    missing_target = next((t for t in targets if t["id"] == 99), None)
    assert missing_target is not None
    assert missing_target["type"] == "NPC"
