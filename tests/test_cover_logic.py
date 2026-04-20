import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.core.common_types import Token

def test_calculate_token_cover_bonuses_no_cover():
    # Setup
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    engine.blocker_mask = np.zeros((100, 100), dtype=np.uint8)
    
    # Mock tokens
    source_token = MagicMock(spec=Token)
    source_token.world_x = 10.0
    source_token.world_y = 10.0
    
    target_token = MagicMock(spec=Token)
    target_token.world_x = 50.0
    target_token.world_y = 50.0
    
    # We need to mock _calculate_token_footprint_with_planes or set up the engine properly
    # For now, let's assume we can mock the internal call to _numba_calculate_cover_grade
    # OR we can test the high level logic if we implement the wrapper.
    
    # Since I'm doing TDD, I'll write the test for the function that doesn't exist yet.
    from light_map.visibility.visibility_engine import calculate_token_cover_bonuses
    
    # Force cover grade to 0.0 (no cover)
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("light_map.visibility.visibility_engine._numba_calculate_cover_grade", lambda *args: 0.0)
        mp.setattr("light_map.visibility.visibility_engine._numba_trace_path", lambda *args: 0) # Clear path
        
        # We also need to mock _get_footprint_pixels or similar
        def mock_get_pixels(token, engine):
            return np.array([[0, 0]], dtype=np.int32)
        mp.setattr("light_map.visibility.visibility_engine.VisibilityEngine._get_token_boundary_pixels", mock_get_pixels)
        
        ac_bonus, reflex_bonus = calculate_token_cover_bonuses(source_token, target_token, engine)
        
    assert ac_bonus == 0
    assert reflex_bonus == 0

def test_calculate_token_cover_bonuses_partial_cover():
    from light_map.visibility.visibility_engine import calculate_token_cover_bonuses
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    source_token = MagicMock(spec=Token)
    target_token = MagicMock(spec=Token)
    
    with pytest.MonkeyPatch().context() as mp:
        # Partial cover is > 0.0
        mp.setattr("light_map.visibility.visibility_engine._numba_calculate_cover_grade", lambda *args: 0.5)
        def mock_get_pixels(token, engine):
            return np.array([[0, 0]], dtype=np.int32)
        mp.setattr("light_map.visibility.visibility_engine.VisibilityEngine._get_token_boundary_pixels", mock_get_pixels)
        
        ac_bonus, reflex_bonus = calculate_token_cover_bonuses(source_token, target_token, engine)
        
    assert ac_bonus == 2
    assert reflex_bonus == 2

def test_calculate_token_cover_bonuses_superior_cover():
    from light_map.visibility.visibility_engine import calculate_token_cover_bonuses
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    source_token = MagicMock(spec=Token)
    target_token = MagicMock(spec=Token)
    
    with pytest.MonkeyPatch().context() as mp:
        # Superior cover is > 0.5
        mp.setattr("light_map.visibility.visibility_engine._numba_calculate_cover_grade", lambda *args: 0.75)
        def mock_get_pixels(token, engine):
            return np.array([[0, 0]], dtype=np.int32)
        mp.setattr("light_map.visibility.visibility_engine.VisibilityEngine._get_token_boundary_pixels", mock_get_pixels)
        
        ac_bonus, reflex_bonus = calculate_token_cover_bonuses(source_token, target_token, engine)
        
    assert ac_bonus == 5
    assert reflex_bonus == 5
