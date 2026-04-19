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
- **Token State:** Add `cover_bonus` (int) and `reflex_bonus` (int) as optional fields to the `Token` class in `src/light_map/core/common_types.py`.

### 2. SVG Extraction & Layer Detection
- **File:** `src/light_map/rendering/svg/utils.py`
- **Detection Logic:** Update `get_visibility_type(label: str)` to detect layers containing both "low" and "object".
- **Shape Handling:** All shapes in these layers must be extracted as closed polygons.

### 3. Mask Representation
- **Constant:** Add `MASK_VALUE_LOW = 50` to `src/light_map/visibility/visibility_engine.py`.
- **Storage:** Render low objects into the `blocker_mask` (uint8) using `cv2.fillPoly` with the value `50`.

### 4. Visibility Algorithm: The "Best Vantage" $N^2$ Check
We'll implement a new Numba-optimized function in `VisibilityEngine`:

#### `_numba_calculate_cover_grade`
```python
@njit(cache=True)
def _numba_calculate_cover_grade(
    pc_border_xs, pc_border_ys,
    npc_border_xs, npc_border_ys,
    blocker_mask, grid_spacing_svg,
    thirty_feet_px
):
    # pc_border: boundary pixels of the PC token
    # npc_border: boundary pixels of the target NPC token
    
    total_npc_pixels = len(npc_border_xs)
    obscured_pixels = 0
    visible_pixels = 0
    
    for i in range(total_npc_pixels):
        nx, ny = npc_border_xs[i], npc_border_ys[i]
        is_pixel_visible = False
        is_pixel_obscured = False
        
        for j in range(len(pc_border_xs)):
            px, py = pc_border_xs[j], pc_border_ys[j]
            
            # 1. Trace path and check for blockers (Wall=255, Door=200, Low=50)
            # path_result: 0=Clear, 1=Blocked (Wall/Door), 2=Obscured (Low Object)
            path_result = _numba_trace_path(px, py, nx, ny, blocker_mask)
            
            if path_result == 0:
                is_pixel_visible = True
                is_pixel_obscured = False
                break # Attacker chose their best vantage
            elif path_result == 2:
                # 2. Check 30ft and proximity conditions
                # (Pseudocode for distance checks)
                dist_npc_obj = ... # Distance from NPC pixel to the obstacle intersection
                if dist_npc_obj < thirty_feet_px:
                     is_pixel_visible = True
                     is_pixel_obscured = True
        
        if is_pixel_visible:
            visible_pixels += 1
            if is_pixel_obscured:
                obscured_pixels += 1
            
    # Calculate Grade: (obscured_pixels / visible_pixels) if visible_pixels > 0
    # ...
```

### 5. Component Updates
- **`visibility_engine.py`**: 
  - Add `_numba_trace_path` to return 0, 1, or 2 based on the encountered blocker type.
  - Add `calculate_token_cover_bonuses(source_token, target_token)` method.
- **`interactive_app.py`**: 
  - Update `process_state` to calculate cover bonuses for all visible tokens during Exclusive Vision.
- **`TacticalOverlayLayer` (New)**: 
  - A new layer that renders floating text labels below visible target tokens.

## Testing Strategy
- **Unit Tests:** Verify SVG extraction correctly identifies low object layers.
- **Logic Tests:** 
  - Test the 30-foot proximity rule for low objects.
  - Test "Best Vantage" (attacker choosing their best corner).
  - Test the three cover grades (+2, +4, +8).
- **Performance:** Ensure $N^2$ calculations for visible tokens don't stall the main loop.
