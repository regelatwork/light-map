import numpy as np
import cv2
import pytest
from light_map.visibility_engine import VisibilityEngine

def test_token_footprint_expansion():
    # 100 svg = 16 px. Center = 8px.
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    
    # Create a small blocker mask (32x32)
    # A wall at x=12 (vertical)
    engine.blocker_mask = np.zeros((32, 32), dtype=np.uint8)
    engine.blocker_mask[:, 12] = 255 
    
    # Token size 1 (16px wide, so +/- 8px from center)
    # Expansion +1px means +/- 9px. 
    # From x=8, expansion goes to x=17. But wall is at x=12.
    footprint = engine._calculate_token_footprint(8, 8, size=1)
    
    # Should stop at x=11 (just before wall)
    assert np.max(np.where(footprint > 0)[1]) < 12
    # Should reach at least x=11
    assert np.max(np.where(footprint > 0)[1]) == 11
    
def test_token_footprint_no_wall():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    engine.blocker_mask = np.zeros((32, 32), dtype=np.uint8)
    
    # Token size 1 (16px) -> +/- 8px. Expansion +1px -> +/- 9px.
    # Center (16, 16). Range 7 to 25.
    footprint = engine._calculate_token_footprint(16, 16, size=1)
    
    # Check bounds
    coords = np.where(footprint > 0)
    assert np.min(coords[1]) == 7  # 16 - 9
    assert np.max(coords[1]) == 25 # 16 + 9
    assert np.min(coords[0]) == 7
    assert np.max(coords[0]) == 25
