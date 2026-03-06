# Design: Pixel-Based Visibility Engine (Watertight LOS)

## Overview
Light Map currently uses a mathematical raycasting approach (Starfinder 1e style) to calculate visibility polygons. This approach suffers from "leaky walls" when SVG segments do not perfectly abut and "grid spillover" when walls don't align with the 1" grid.

This design replaces raycasting with a **Pixel-Based Visibility Engine** that uses a high-resolution "Blocker Mask" to ensure watertight connectivity and natural "corner peeking" for tokens.

## Core Concepts

### 1. The Blocker Mask (Watertight Physicality)
We move from mathematical segments to a physical pixel grid.
- **Resolution:** 1/16th of an inch per pixel (matches the FoW system).
- **Rendering:** SVG wall and closed-door segments are drawn with:
    - **Thickness:** 2 pixels.
    - **Round Caps:** Circles at every vertex to ensure gapless connectivity at any angle.
- **Windows:** Transparent to vision (not rendered in the blocker mask).

### 2. Token Footprint & "Peeking"
Tokens are no longer treated as points. We calculate a **Source Footprint** to allow natural illumination of hallways around corners.
- **Flood Fill:** A BFS fill from the token's center on the Blocker Mask.
- **Bounds:** Stops at walls OR at the "natural grid boundary" (token size) **plus 1 pixel**.
- **Source Pixels:** All pixels on the boundary of this filled area become potential light sources.

### 3. Visibility Algorithm (Optimized Mask-Centric)
The engine produces a `uint8` **Vision Mask** (0=hidden, 255=visible) directly.
- **Step 1: Reachability Fill:** A BFS from the token's center to find all pixels not blocked by walls.
- **Step 2: LOS Verification (Vectorized):** For each reachable pixel, check if a clear line (uninterrupted by the Blocker Mask) exists to **any** Source Pixel.
- **Step 3: Mask Union:** The final mask is the union of these clear LOS paths.

## API Changes
- **Deprecation:** The `calculate_visibility` method (returning a polygon) is deprecated in favor of `get_token_vision_mask`.
- **Mask-Centric:** All vision updates are handled as binary masks.
- **Tests:** Update unit tests to verify mask density and shape using OpenCV (`cv2.countNonZero`, `cv2.matchShapes`) instead of point-matching.

## Success Criteria
1. **Watertight:** No "light leaks" through wall joints or small SVG gaps.
2. **Corner Peeking:** Tokens pushed against a corner can illuminate the adjacent hallway.
3. **No Spillover:** Light does not "spill" through a wall even if the wall is not perfectly aligned with the grid.
4. **Performance:** Vision calculation remains efficient for "Sync Vision" and "Token Inspection" workflows (targeting <100ms per token).
