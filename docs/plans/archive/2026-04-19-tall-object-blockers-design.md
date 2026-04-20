# Tall Object Blockers Design

## Overview
This design introduces "Tall Objects" to the visibility system. Unlike walls, which are opaque, tall objects represent elevated terrain or structures where the top surface is visible, but the area behind it is obscured.

## Goals
- Allow visibility "into" and "on top of" tall objects.
- Block visibility "behind" tall objects from the viewer's perspective.
- Implement "High Ground" logic: tokens standing on a tall object can see down into open space.
- Handle adjacent tall objects as a continuous elevated area.

## Technical Specifications

### 1. Data Model & Mirroring
- **Python:** Add `TALL_OBJECT = "tall_object"` to `VisibilityType` in `src/light_map/visibility/visibility_types.py`.
- **Frontend:** Add `TALL_OBJECT = "tall_object"` to the `VisibilityType` enum in `frontend/src/types/system.ts`.
- **Sync:** Ensure `tests/test_enum_sync.py` passes.

### 2. SVG Extraction & Layer Detection
- **File:** `src/light_map/rendering/svg/utils.py`
- **Detection Logic:** Update `get_visibility_type(label: str)` to detect layers containing both "tall" and "object":
  ```python
  id_lower = label.lower()
  if "tall" in id_lower and "object" in id_lower:
      return VisibilityType.TALL_OBJECT, False
  ```
- **Shape Handling:** All shapes in these layers must be extracted as closed polygons. Ensure `extract_visibility_blocker` correctly closes paths if necessary.

### 3. Mask Representation
- **Constant:** Add `MASK_VALUE_TALL = 100` to `src/light_map/visibility/visibility_engine.py`.
- **Storage:** Tall objects are rendered into the existing `blocker_mask` (uint8) using `cv2.fillPoly` with the value `100`. This avoids the overhead of a separate mask.

### 4. Visibility Algorithm: The "First Exit" Rule
The line-of-sight (LOS) algorithm (`_numba_is_line_obstructed`) will be updated to handle elevation transitions.

#### Viewer Context
The `viewer_starts_in_tall` flag is calculated once per calculation using the viewer's center:
`viewer_starts_in_tall = (blocker_mask[int(cy), int(cx)] == MASK_VALUE_TALL)`

#### Numba-Optimized LOS
```python
@njit(cache=True)
def _numba_is_line_obstructed(x1, y1, x2, y2, blocker_mask, viewer_starts_in_tall):
    # If viewer starts on ground, they have already 'exited' the tall zone
    has_exited_initial_tall_zone = not viewer_starts_in_tall
    
    # ... step through pixels along line ...
    val = blocker_mask[py, px]
    
    if val == 255 or val == 200: # WALL or DOOR_CLOSED
        return True
    
    if val == 0: # OPEN SPACE
        has_exited_initial_tall_zone = True
    elif val == 100: # TALL OBJECT
        if has_exited_initial_tall_zone:
            return True # Blocked: Exit from ground or second exit
            
    return False
```

### 5. Component Updates
- **`visibility_engine.py`**: 
  - Update `update_blockers` to fill tall object polygons.
  - Update `_numba_bfs_flood_fill` and `_calculate_visibility` to pass the `viewer_starts_in_tall` flag.
- **`fow_manager.py`**: Ensure tall objects are correctly marked as "discovered" when visible.

## Testing Strategy
- **Unit Tests:** Verify SVG extraction correctly identifies tall object layers and closes shapes.
- **Logic Tests:** Test LOS between points:
  - Ground -> Plateau (Should see plateau surface).
  - Ground -> Ground behind Plateau (Should be blocked).
  - Plateau -> Ground (Should see ground).
  - Plateau A -> Ground -> Plateau B (Should see Plateau B surface, but not behind it).
- **Performance:** Ensure Numba execution remains efficient with the extra conditional.
