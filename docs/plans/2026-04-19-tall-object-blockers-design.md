# Tall Object Blockers Design

## Overview
This design introduces "Tall Objects" to the visibility system. Unlike walls, which are opaque, tall objects represent elevated terrain or structures where the top surface is visible, but the area behind it is obscured.

## Goals
- Allow visibility "into" and "on top of" tall objects.
- Block visibility "behind" tall objects from the viewer's perspective.
- Implement "High Ground" logic: tokens standing on a tall object can see down into open space.
- Handle adjacent tall objects as a continuous elevated area.

## Architecture

### 1. SVG Extraction
- **Layer Detection:** Identify layers where the name contains both "tall" and "object" (case-insensitive, any order).
- **Shape Handling:** Extract all shapes (Paths, Rects, Circles, etc.) as closed polygons.
- **Type:** Assign `VisibilityType.TALL_OBJECT`.

### 2. Mask Representation
- **Tall Mask:** A high-resolution bitmask where pixels inside tall object polygons are marked (`MASK_VALUE_TALL`).
- **Collision Mask:** Tall object boundaries will be rendered into the existing `blocker_mask` to ensure they act as physical boundaries for token footprints when necessary.

### 3. Visibility Algorithm: The "First Exit" Rule
The line-of-sight (LOS) algorithm (`_numba_is_line_obstructed`) will be updated to track the "First Exit" state:

- **State:** `has_exited_initial_tall_zone` (Boolean, starts False).
- **Initial Check:** If the Viewer's center is in `OPEN` space, `has_exited_initial_tall_zone` is set to True immediately.
- **Traversal:**
  - As the line moves from pixel {i}$ to {i+1}$:
  - If {i} == TALL$ and {i+1} == OPEN$:
    - If `has_exited_initial_tall_zone` is True: **BLOCK** (This is a second exit or an exit from the ground).
    - Else: Set `has_exited_initial_tall_zone = True` and **CONTINUE**.
  - Standard `WALL` and `CLOSED_DOOR` checks remain as absolute blockers.

### 4. Component Updates
- **`VisibilityType`**: Add `TALL_OBJECT`.
- **`svg/utils.py`**: Add layer-based type detection for tall objects.
- **`visibility_engine.py`**: 
  - Update `update_blockers` to render the tall object mask.
  - Update Numba-optimized LOS and BFS functions to implement the "First Exit" rule.
- **`fow_manager.py`**: Ensure tall objects are correctly marked as "discovered" when seen.

## Testing Strategy
- **Unit Tests:** Verify SVG extraction correctly identifies tall object layers and closes shapes.
- **Logic Tests:** Test LOS between points:
  - Ground -> Plateau (Should see plateau surface).
  - Ground -> Ground behind Plateau (Should be blocked).
  - Plateau -> Ground (Should see ground).
  - Plateau A -> Ground -> Plateau B (Should see Plateau B surface, but not behind it).
- **Performance:** Ensure the Numba-optimized LOS check remains performant with the extra state bit.
