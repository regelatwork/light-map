import numpy as np
import pytest
from light_map.visibility.visibility_engine import VisibilityEngine, MASK_VALUE_TALL, MASK_VALUE_WALL
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker

def test_wall_priority_over_tall_object():
    """
    Verifies that a Wall (255) correctly overwrites a Tall Object (100) surface
    regardless of extraction order, preventing vision leaks.
    """
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    engine.svg_to_mask_scale = 1.0 # 1px = 1 unit for easy testing
    
    # 1. Create a large Tall Object (0,0) to (10,10)
    tall_blocker = VisibilityBlocker(
        points=[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        type=VisibilityType.TALL_OBJECT,
        layer_name="Tall Objects",
        id="tall1"
    )
    
    # 2. Create a Wall inside that Tall Object area (5,0) to (5,10)
    wall_blocker = VisibilityBlocker(
        points=[(5, 0), (5, 10)],
        type=VisibilityType.WALL,
        layer_name="Walls",
        id="wall1"
    )
    
    # Render with Wall SECOND (Normal priority test)
    engine.update_blockers([tall_blocker, wall_blocker], mask_width=20, mask_height=20)
    assert engine.blocker_mask[5, 5] == MASK_VALUE_WALL # Opaque priority
    
    # Render with Wall FIRST (This used to fail: the tall object would overwrite it)
    engine.update_blockers([wall_blocker, tall_blocker], mask_width=20, mask_height=20)
    assert engine.blocker_mask[5, 5] == MASK_VALUE_WALL # MUST stay opaque
    
    # Verify identification of the wall
    # Since ID map tracks which object is at which pixel, and the wall was rendered second, 
    # it should be the wall's ID (which is index 0 in the list [wall, tall]).
    assert engine.blocker_id_map[5, 5] == 0
