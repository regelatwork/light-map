# Implementation Plan: Tactical Cover "Cone of Fire" Overlay

## Objective
Enhance the existing Tactical Cover and Reflex feature by visually representing the "Cone of Fire" from the selected token to visible enemies. This provides immediate, intuitive feedback on the source of the cover bonus, visualizing the Starfinder 1e "best corner" rule.

## Key Files & Context
- `src/light_map/visibility/visibility_engine.py`: Responsible for calculating cover grades using Numba.
- `src/light_map/rendering/layers/tactical_overlay_layer.py`: Responsible for drawing the tactical labels and now the cone wedges.
- `src/light_map/core/common_types.py`: Will include the `CoverResult` and `WedgeSegment` data structures.

## Implementation Steps

### 1. Define Data Structures (`common_types.py`)
Add the following to support efficient data transfer:
```python
@dataclass
class WedgeSegment:
    start_idx: int
    end_idx: int
    status: int  # 0: Clear, 2: Obscured (1: Blocked is filtered out)

@dataclass
class CoverResult:
    ac_bonus: int
    reflex_bonus: int
    best_apex: Tuple[int, int]  # (x, y) in mask space
    segments: List[WedgeSegment]
```

### 2. Update Visibility Engine (`visibility_engine.py`)
- **Apex Selection**: Modify `_numba_calculate_cover_grade` to return the `best_apex_index`. If multiple indices share the same best ratio, use `median_index = indices[len(indices)//2]`.
- **Near-Side Filtering**: 
    - For each target pixel $P$, center $C$, and apex $A$:
    - Condition: `(P_x - C_x)*(P_x - A_x) + (P_y - C_y)*(P_y - A_y) <= 0`.
    - Only pixels satisfying this are eligible for the visual cone (Choice A).
- **Segment Extraction**: 
    - Within `calculate_token_cover_bonuses`, iterate through the `npc_pixels` using the `best_apex`.
    - Group contiguous sequences of `status=0` or `status=2` into `WedgeSegment` objects.
    - Status `1` (Blocked) results in no segment.
### 3. Rendering Logic (`tactical_overlay_layer.py`)
- **Pixel Ordering**: Ensure `npc_pixels` are sorted by their polar angle relative to the `best_apex` before segment extraction. This ensures that "contiguous indices" in the data structure translate to contiguous geometric wedges in the rendering.
- **Coordinate Transform**: Convert `best_apex` and `npc_pixels` from Mask Space to Screen Space. Remember to scale Mask Space coordinates by `1/svg_to_mask_scale` before passing them to `map_system.world_to_screen`.
- **Polygon Creation**: For each `WedgeSegment`, create a polygon: `[Apex, Pixel[start], Pixel[start+1], ..., Pixel[end]]`.
...
- **Stipple Texture**:
    - Create a 4x4 screen-pixel tile: `tile = [[255,0,0,0],[0,0,0,0],[0,0,255,0],[0,0,0,0]]`.
    - Use `np.tile` to create a `stipple_mask` the size of the patch.
- **Rendering Pass**:
    - **Clear (status 0)**: `cv2.fillPoly` with Cyan (BGR: 255, 255, 0) at 15% alpha.
    - **Obscured (status 2)**: `cv2.fillPoly` to create a `wedge_mask`, then `cv2.bitwise_and(wedge_mask, stipple_mask)` to apply the pattern.
- **Outlines**: Draw 1px white lines (`(255, 255, 255)`) from the Apex to `Pixel[start]` and `Pixel[end]`.

### 4. Integration
- Update `WorldState`'s `tactical_bonuses` atom to store `Dict[int, CoverResult]`.

## Verification & Testing
- **Unit Tests**: Add tests to `tests/test_tactical_cover_logic.py` verifying `WedgeSegment` extraction logic and Near-Side filtering math.
- **Integration**: Verify the `TacticalOverlayLayer` versioning correctly picks up changes to `tactical_bonuses`.
