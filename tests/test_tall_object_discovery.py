import pytest
import numpy as np
from light_map.visibility.fow_manager import FogOfWarManager
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType

def test_tall_object_discovery_in_fow():
    """
    Tests that tall objects are marked as 'discovered' in the FogOfWarManager
    when they are within the visibility mask.
    """
    width, height = 100, 100
    fow = FogOfWarManager(width, height)
    engine = VisibilityEngine(grid_spacing_svg=1.0)
    
    # Define a tall object: 1x1 square at (2, 2) -> (3, 3)
    # Mask space: (32, 32) -> (48, 48)
    tall_blocker = VisibilityBlocker(
        id="tall_pillar",
        points=[(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)],
        type=VisibilityType.TALL_OBJECT,
        layer_name="tall"
    )
    
    engine.update_blockers([tall_blocker], mask_width=width, mask_height=height)
    
    # Get visibility mask from a position that can see the pillar
    # Viewer at (1, 1)
    vis_mask, discovered_ids = engine.get_token_vision_mask(
        token_id=1, origin_x=1.0, origin_y=1.0, size=1,
        vision_range_grid=50.0, mask_width=width, mask_height=height
    )
    
    assert "tall_pillar" in discovered_ids, "Tall pillar should be in discovered_ids from engine"
    
    # Reveal area in FoW
    fow.reveal_area(vis_mask, discovered_ids)
    
    # Check if it's discovered in FoW
    # Note: We might want to check a more generic attribute name if we rename it
    assert "tall_pillar" in fow.discovered_ids, "Tall pillar should be discovered in FoW"

def test_tall_object_area_revealed_in_fow():
    """
    Tests that the area occupied by a tall object is correctly revealed (not shrouded)
    in the explored mask of FogOfWarManager.
    """
    width, height = 400, 400
    fow = FogOfWarManager(width, height)
    engine = VisibilityEngine(grid_spacing_svg=1.0)
    
    # Define a tall object: 5x5 square at (10, 10) -> (15, 15)
    # Scale is 16.0, so (160, 160) -> (240, 240) in mask space
    tall_blocker = VisibilityBlocker(
        id="plateau",
        points=[(10, 10), (15, 10), (15, 15), (10, 15), (10, 10)],
        type=VisibilityType.TALL_OBJECT,
        layer_name="tall"
    )
    
    engine.update_blockers([tall_blocker], mask_width=width, mask_height=height)
    
    # Viewer at (5, 5) can see the plateau top
    vis_mask, _ = engine.get_token_vision_mask(
        token_id=1, origin_x=5.0, origin_y=5.0, size=1,
        vision_range_grid=50.0, mask_width=width, mask_height=height
    )
    
    # Plateau top should be visible (255)
    target_mx = int(12.0 * engine.svg_to_mask_scale)
    target_my = int(12.0 * engine.svg_to_mask_scale)
    assert vis_mask[target_my, target_mx] == 255, "Plateau top should be visible in LOS mask"
    
    # Reveal in FoW
    fow.reveal_area(vis_mask)
    
    # Check if explored mask has the plateau top revealed
    assert fow.explored_mask[target_my, target_mx] == 255, "Plateau top should be explored in FoW"
