import numpy as np
from light_map.visibility.visibility_engine import (
    VisibilityEngine,
    MASK_VALUE_LOW,
    MASK_VALUE_WALL,
)
from light_map.core.common_types import Token


def test_calculate_cover_bonuses_starfinder_rules():
    """
    End-to-end test of the cover calculation logic using real Numba functions.
    Verifies Partial, Standard, and Improved cover thresholds.
    """
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    engine.svg_to_mask_scale = 1.0  # 1px = 1 unit for easy math

    # 100x100 mask
    engine.blocker_mask = np.zeros((100, 100), dtype=np.uint8)

    # Source at (10, 10), Size 1 (Medium)
    source = Token(id=1, world_x=10, world_y=10, size=1)

    # Target at (50, 10), Size 1
    target = Token(id=2, world_x=50, world_y=10, size=1)

    # --- SCENARIO 1: NO COVER ---
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    assert ac == 0
    assert reflex == 0

    # --- SCENARIO 2: PARTIAL COVER (+2/+1) ---
    # Put a tiny Low Object between them, close to target
    # 1 pixel wide. Ratio will be small.
    engine.blocker_mask[9:11, 45] = MASK_VALUE_LOW
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    assert ac == 2
    assert reflex == 1

    # --- SCENARIO 3: STANDARD COVER (+4/+2) ---
    # Larger Low Object.
    engine.blocker_mask[5:15, 45] = MASK_VALUE_LOW
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    assert ac == 4
    assert reflex == 2

    # --- SCENARIO 4: NO IMPROVED COVER FROM LOW OBJECTS ---
    # Even if blocked 100% by Low Objects, should only be +4
    engine.blocker_mask[0:100, 45] = MASK_VALUE_LOW
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    assert ac == 4
    assert reflex == 2

    # --- SCENARIO 5: IMPROVED COVER (+8/+4) FROM WALLS ---
    # Must be 90%+ blocked by WALLS from the BEST corner.
    engine.blocker_mask.fill(0)
    # Target is Medium (size 1) -> approx 64 border pixels (4 * 16).
    # To hit 90%, we need to block approx 58 pixels.
    # I'll block a large vertical slice and leave only 2 pixels open.
    engine.blocker_mask[0:100, 42:58] = MASK_VALUE_WALL
    engine.blocker_mask[10, 42:58] = 0  # 1-pixel high horizontal slit
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    assert ac == 8
    assert reflex == 4

    # --- SCENARIO 6: TOTAL COVER (-1/-1) ---
    # Massive wall, no gaps.
    engine.blocker_mask.fill(0)
    engine.blocker_mask[0:100, 20:80] = MASK_VALUE_WALL
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    assert ac == -1
    assert reflex == -1

    # --- SCENARIO 7: PROXIMITY RULE (NO COVER) ---
    # Put low object close to ATTACKER (x=15)
    engine.blocker_mask.fill(0)
    engine.blocker_mask[0:100, 15] = MASK_VALUE_LOW
    res = engine.calculate_token_cover_bonuses(source, target)
    ac, reflex = res.ac_bonus, res.reflex_bonus
    # Target (x=50) is NOT closer to obstacle (x=15) than attacker (x=10)
    assert ac == 0
    assert reflex == 0


def test_proximity_30ft_rule():
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    engine.svg_to_mask_scale = 1.0
    engine.blocker_mask = np.zeros((200, 200), dtype=np.uint8)

    source = Token(id=1, world_x=10, world_y=10, size=1)
    # Target at (150, 10). Dist = 140.
    target = Token(id=2, world_x=150, world_y=10, size=1)

    # Low object at x=50. Dist to target = 100 (> 96px / 30ft)
    engine.blocker_mask[:, 50] = MASK_VALUE_LOW
    res = engine.calculate_token_cover_bonuses(source, target)
    assert res.ac_bonus == 0  # Too far

    # Low object at x=100. Dist to target = 50 (< 96px)
    engine.blocker_mask.fill(0)
    engine.blocker_mask[:, 100] = MASK_VALUE_LOW
    res = engine.calculate_token_cover_bonuses(source, target)
    assert res.ac_bonus > 0  # Should provide cover
