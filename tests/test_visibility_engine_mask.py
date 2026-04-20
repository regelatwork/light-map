from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType

def test_tall_object_mask_rendering():
    # 16 units per grid cell is the default scale used in VisibilityEngine
    engine = VisibilityEngine(grid_spacing_svg=1.0)
    
    # Define a rectangular tall object in SVG coordinates
    # VisibilityEngine scale is 16.0 / grid_spacing_svg = 16.0
    # So (1, 1) to (3, 3) in SVG becomes (16, 16) to (48, 48) in mask
    points = [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]
    blocker = VisibilityBlocker(
        points=points,
        type=VisibilityType.TALL_OBJECT,
        layer_name="Objects"
    )
    
    # Initialize engine with a sufficient size
    engine.update_blockers([blocker], mask_width=100, mask_height=100)
    
    # Check a point inside the polygon (e.g., (2.0, 2.0) -> (32, 32))
    assert engine.blocker_mask[32, 32] == 100 # MASK_VALUE_TALL
    
    # Check another point inside
    assert engine.blocker_mask[20, 20] == 100
    
    # Check a point outside (e.g., (0.5, 0.5) -> (8, 8))
    assert engine.blocker_mask[8, 8] == 0
