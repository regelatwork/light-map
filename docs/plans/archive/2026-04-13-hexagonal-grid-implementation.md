# Implementation Plan: Hexagonal Grid Support

## Overview
Adds hexagonal grid support across the full stack (backend, frontend, state, and visibility).

## Steps

### 1. Core Schema and Shared Geometry
- [ ] **Geometry Utility**: Create `src/light_map/core/geometry.py`.
    - Implement `PointyTopHex` and `FlatTopHex` classes with `to_pixel`, `from_pixel`, and `round` methods.
    - Reference formulas from `features/hexagonal_grid_support.md`.
- [ ] **Common Types**: Add `GridType` enum to `src/light_map/core/common_types.py`.
- [ ] **World State Update**: 
    - Add `grid_type` property to `GridMetadata` dataclass in `common_types.py`.
    - Update `WorldState` property `grid_spacing_svg` and friends to preserve/update the new `type` field in the `GridMetadata` atom.
- [ ] **Config Schema**: 
    - Update `MapEntrySchema` in `src/light_map/core/config_schema.py` to include `grid_type`.
    - Run `python3 scripts/generate_ts_schema.py`.

### 2. Rendering Layers
- [ ] **MapGridLayer**: Update `_generate_patches` in `src/light_map/rendering/layers/map_grid_layer.py`.
    - If `type` is hexagonal, calculate a bounding box of visible axial coordinates.
    - Draw vertices for each hexagon using `cv2.polylines`.

### 3. Vision and Snapping
- [ ] **Token Filter**: Update `src/light_map/vision/processing/token_filter.py`.
    - Add `_apply_hex_snapping` helper using the shared geometry utility.
    - Branch `_apply_grid_snapping` to call either square or hex snapping.

### 4. Visibility Engine
- [ ] **Boundary Plane Calculation**: Add a method to `VisibilityEngine` to generate the 6 linear inequalities ($ax + by + c \le 0$) for a hex cell.
- [ ] **BFS Footprint**: Update `_calculate_token_footprint` to perform the same-side test against these planes.
- [ ] **Numba Optimization**: Update `_numba_bfs_flood_fill` and its caller in `src/light_map/visibility/visibility_engine.py` to pass plane coefficients and enforce boundaries in the JIT loop.

### 5. Frontend UI and Rendering
- [ ] **Type Definitions**: Verify `frontend/src/types/system.ts` correctly reflects the new `GridType`.
- [ ] **GridLayer Component**: Update `frontend/src/components/GridLayer.tsx`.
    - Add `HexMesh` rendering logic (generating a large `<path d="..." />` string for the entire view).
    - Update scale handle calculations to be geometry-aware.
- [ ] **UI Controls**: Update `frontend/src/components/SettingsModal.tsx`.
    - Add the "Grid Type" selector to the "Grid & Map" tab.

## Verification Strategy
- [ ] **Unit Tests**: Create `tests/test_hex_geometry.py` to verify conversions and rounding accuracy.
- [ ] **Integration Tests**: Extend `tests/test_aruco_grid_snapping.py` with hexagonal test cases.
- [ ] **Visual Check**: Run the app, select a hex grid, and verify:
    - [ ] Grid lines align with the map.
    - [ ] Token reveals the exact hex cell boundary.
    - [ ] Visibility is blocked by walls correctly within a hex.
