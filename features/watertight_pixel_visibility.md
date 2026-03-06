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

### 2.3 Visibility BFS & LOS Filtering

Vision is calculated using a custom Cartesian BFS propagation:

1. **Propagation:** Visibility spreads from the token's edge pixels into reachable areas.
1. **Straight-Line LOS:** Each candidate pixel must have an unobstructed straight line (verified against the Blocker Mask) to at least one pixel on the token's footprint perimeter.
1. **Watertightness:** The combination of 2px round-capped walls and pixel-precise LOS checks ensures zero light leakage.

## 3. Technical Specifications

### 3.1 Performance & Workflow

- **Manual Sync:** Vision is updated when the user selects "Sync Vision" or during single-token "Inspection" mode.
- **Implementation:** Custom BFS with vectorized NumPy line-of-sight verification.

### 3.2 API Transition

- **Mask-Centric:** The engine directly produces a `uint8` vision mask (0=hidden, 255=visible).
- **Deprecation:** The legacy polygon-based `calculate_visibility` method and spatial hashing have been removed.

## 4. Success Criteria

- **No Leaks:** Zero light leakage through wall joints or small SVG gaps.
- **Corner Peeking:** Tokens can illuminate hallways when positioned at corners.
- **No Spillover:** Light stops at the physical wall boundary regardless of grid alignment.
