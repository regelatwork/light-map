# Watertight Pixel-Based Visibility Engine (Implemented)

## 1. Goal
Replace the mathematical raycasting visibility engine with a high-resolution, pixel-based approach. This ensures "watertight" walls (no light leaks through SVG joints), prevents "grid spillover" (where light bypasses walls that aren't perfectly grid-aligned), and enables natural "corner peeking" for tokens.

## 2. Core Concepts

### 2.1 The Blocker Mask
A high-resolution binary mask (1/16" per pixel) represents all physical obstacles.
- **Rendering:** SVG segments are drawn with a 2-pixel width and Round Caps to ensure physical connectivity.
- **Dynamic Blocks:** Closed doors are rendered; windows are omitted (transparent to vision).

### 2.2 Source Footprint (Corner Peeking)
Tokens are treated as area light sources rather than points.
- **Expansion:** A BFS flood fill from the token center, constrained by walls and the token's grid size + 1 pixel of "overhang".
- **Light Sources:** The boundary pixels of this footprint act as the origins for Line-of-Sight (LOS) checks.

### 2.3 Reachability & LOS Filtering
Vision is calculated using an optimized polar shadow-casting approach:
1. **Polar Warp:** The environment around each source point is warped to polar coordinates.
2. **Shadow Casting:** For each angle, the first wall pixel blocks everything beyond it.
3. **Inverse Warp:** Shadows are warped back to Cartesian space and unioned.

## 3. Technical Specifications

### 3.1 Performance & Workflow
- **Manual Sync:** Vision is updated when the user selects "Sync Vision" or during single-token "Inspection" mode.
- **Target Latency:** <100ms per token at 1/16" resolution.

### 3.2 API Transition
- **Mask-Centric:** The engine directly produces a `uint8` vision mask (0=hidden, 255=visible).
- **Deprecation:** The polygon-based `calculate_visibility` method has been removed.

## 4. Success Criteria
- **No Leaks:** Zero light leakage through wall joints or small SVG gaps.
- **Corner Peeking:** Tokens can illuminate hallways when positioned at corners.
- **No Spillover:** Light stops at the physical wall boundary regardless of grid alignment.
