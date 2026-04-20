# Tactical Cover and Reflex Bonuses (Starfinder 1e) Design

## Overview
This design implements automated cover and reflex save bonuses for Starfinder 1e based on "Low Objects" in the SVG map.

## Goals
- Allow visibility through "Low Objects" but provide AC and Reflex bonuses.
- Implement the "Best Vantage" rule: Attacker chooses their best corner (pixel) to see the target.
- Respect the 30-foot obstacle distance and proximity rules for Starfinder 1e.
- Provide real-time floating labels in Exclusive Vision for both PCs and NPCs.

## Technical Specifications

### 1. Data Model & Mirroring
- **Python:** Add `LOW_OBJECT = "low_object"` to `VisibilityType` in `src/light_map/visibility/visibility_types.py`.
- **Frontend:** Add `LOW_OBJECT = "low_object"` to the `VisibilityType` enum in `frontend/src/types/system.ts`.
- **Token State:** Update `Token` in `src/light_map/core/common_types.py` with:
  ```python
  cover_bonus: int = 0
  reflex_bonus: int = 0
  ```
  Update `to_dict()` and any related constructors.

### 2. SVG Extraction & Layer Detection
- **File:** `src/light_map/rendering/svg/utils.py`
- **Detection Logic:** Update `get_visibility_type(label: str)` to detect layers containing both "low" and "object":
  ```python
  id_lower = label.lower()
  if "low" in id_lower and "object" in id_lower:
      return VisibilityType.LOW_OBJECT, False
  ```
- **Shape Handling:** All shapes in these layers must be extracted as closed polygons.

### 3. Mask Representation
- **Constant:** Add `MASK_VALUE_LOW = 50` to `src/light_map/visibility/visibility_engine.py`.
- **Storage:** Render low objects into the `blocker_mask` (uint8) using `cv2.fillPoly` with the value `50`.

### 4. Visibility Algorithm: The "Best Vantage" $N^2$ Check
We'll implement a new Numba-optimized function in `VisibilityEngine`:

#### `_numba_trace_path`
```python
@njit(cache=True)
def _numba_trace_path(x1, y1, x2, y2, blocker_mask):
    """
    Traces a line and returns:
    0: Clear path
    1: Blocked (Wall/Door)
    2: Obscured (Low Object)
    """
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    num_steps = dx if dx > dy else dy
    if num_steps == 0: return 0
    
    found_low = False
    for i in range(num_steps):
        t = i / num_steps
        px, py = int(round(x1 + t*(x2-x1))), int(round(y1 + t*(y2-y1)))
        val = blocker_mask[py, px]
        if val >= 200: return 1 # Wall/Door
        if val == 50: found_low = True
    return 2 if found_low else 0
```

#### `_numba_calculate_cover_grade`
- **Coordinate System:** Mask space (16px = 1 grid square).
- **Proximity Constant:** `THIRTY_FEET_PX = 96`.
- **Logic:** For each NPC boundary pixel, find the **Best Vantage** PC boundary pixel that provides the best visibility (Clear > Obscured > Blocked).
- **Distance Check:** Cover is only granted if Euclidean distance from the NPC pixel to the obstacle intersection is $\le 96$ pixels. (Note: For simplicity, if `path_result == 2`, we can use the distance from the NPC pixel to the PC pixel as a proxy or calculate the first intersection point).

### 5. Component Updates
- **`visibility_engine.py`**: 
  - Add `_numba_trace_path` and `_numba_calculate_cover_grade`.
  - Add `calculate_token_cover_bonuses(source_token, target_token)` method.
- **`interactive_app.py`**: 
  - Update `process_state` to calculate cover bonuses for all visible tokens during Exclusive Vision.
- **`TacticalOverlayLayer` (New)**: 
  - A new layer that renders floating text labels using `cv2.putText` at `(token.screen_x, token.screen_y + offset)` for target tokens.
  - Active only when `inspected_token_id` is not None.

## Testing Strategy
- **Unit Tests:** Verify SVG extraction correctly identifies low object layers.
- **Logic Tests:** 
  - Test the 30-foot proximity rule for low objects.
  - Test "Best Vantage" (attacker choosing their best corner).
  - Test the three cover grades (+2, +4, +8).
- **Performance:** Ensure $N^2$ calculations for visible tokens don't stall the main loop.
