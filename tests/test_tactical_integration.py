import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.core.common_types import Token, SelectionType, SelectionState, CoverResult

@pytest.fixture
def app_with_tokens():
    config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    app = InteractiveApp(config)
    app.current_map_path = "test_map.svg"
    
    # Mock map config to return a default profile
    app.map_config = MagicMock()
    app.map_config.resolve_token_profile.return_value = MagicMock(size=1, type="NPC")
    
    # Mock visibility engine
    app.visibility_engine = MagicMock()
    app.visibility_engine.grid_spacing_svg = 16.0
    app.visibility_engine.blocker_mask = np.zeros((100, 100), dtype=np.uint8)
    app.visibility_engine.calculate_token_cover_bonuses.return_value = CoverResult(
        ac_bonus=4, reflex_bonus=2, best_apex=(0,0), segments=[], npc_pixels=np.empty((0,2)), explanation="Standard"
    )
    
    app.state.tokens = [
        Token(id=1, world_x=50, world_y=50),
        Token(id=2, world_x=100, world_y=100)
    ]
    return app

def test_selection_triggers_tactical_update(app_with_tokens):
    app = app_with_tokens
    state = app.state
    
    # Initially no tactical bonuses
    assert not state.tactical_bonuses
    
    # 1. Set selection (simulating action dispatcher)
    state.selection = SelectionState(type=SelectionType.TOKEN, id="1")
    
    # 2. Run update loop (specifically the tactical part)
    app._update_tactical_bonuses(state)
    
    # 3. Verify bonuses are calculated
    assert 2 in state.tactical_bonuses
    assert state.tactical_bonuses[2].ac_bonus == 4
    
    # 4. Deselect
    state.selection = SelectionState(type=SelectionType.NONE, id=None)
    app._update_tactical_bonuses(state)
    
    # 5. Verify bonuses are cleared
    assert not state.tactical_bonuses

def test_token_movement_triggers_tactical_recalculation(app_with_tokens):
    app = app_with_tokens
    state = app.state
    
    state.selection = SelectionState(type=SelectionType.TOKEN, id="1")
    app._update_tactical_bonuses(state)
    
    # Record first calculation version
    first_version = app._last_tactical_calc_version
    
    # Reset mock to track new calls
    app.visibility_engine.calculate_token_cover_bonuses.reset_mock()
    
    # Move a token (trigger update via setter to increment version)
    new_tokens = [t.copy() for t in state.tokens]
    new_tokens[1].world_x += 10
    state.tokens = new_tokens
    
    app._update_tactical_bonuses(state)
    
    # Verify it was recalculated
    assert app.visibility_engine.calculate_token_cover_bonuses.called
    assert app._last_tactical_calc_version > first_version

def test_soft_cover_augmentation(app_with_tokens):
    app = app_with_tokens
    state = app.state
    
    # Add a third token to act as soft cover
    state.tokens.append(Token(id=3, world_x=75, world_y=75))
    state.selection = SelectionState(type=SelectionType.TOKEN, id="1")
    
    # Capture calls to calculate_token_cover_bonuses
    app._update_tactical_bonuses(state)
    
    # Check if augmented mask was used (it should have stamped token 3)
    # We can verify this by checking if stamp_token_footprint was called on the engine
    assert app.visibility_engine.stamp_token_footprint.called
    # It should be called for token 3 when calculating cover for token 2
    # and for token 2 when calculating cover for token 3
    assert app.visibility_engine.stamp_token_footprint.call_count >= 2
