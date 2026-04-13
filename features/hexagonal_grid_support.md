# Feature: Hexagonal Grid Support

## Overview
Adds support for hexagonal grids as a per-map configuration option. This includes visual rendering of the grid (both backend and frontend), token snapping to hexagonal cells, and grid-aware visibility masking.

## Goals
- Support two hexagonal orientations: **Pointy Top** and **Flat Top**.
- Ensure backward compatibility with existing **Square** grids.
- Implement precise token snapping using axial/cube coordinate systems.
- Update the visibility engine to use hexagonal cell boundaries for the initial token footprint.
- Provide a synchronized frontend UI for grid configuration and rendering.

## Design

### 1. Configuration & Schema
A new `GridType` enum will be added to `core/common_types.py` and mirrored in the frontend.

```python
class GridType(StrEnum):
    SQUARE = "SQUARE"
    HEX_POINTY = "HEX_POINTY"  # Pointy side up
    HEX_FLAT = "HEX_FLAT"      # Flat side up
```

`GridMetadata` will be updated to include the grid type:
```python
@dataclass
class GridMetadata:
    spacing_svg: float = 0.0
    origin_svg_x: float = 0.0
    origin_svg_y: float = 0.0
    type: GridType = GridType.SQUARE
```

### 2. Geometry & Rendering (Shared)
A new utility `src/light_map/core/geometry.py` will provide shared math for both backend and frontend.

- **Axial-to-Pixel Transformation**:
    - **Pointy Top**: 
        - $x = size \cdot \sqrt{3} \cdot (q + r/2)$
        - $y = size \cdot \frac{3}{2} \cdot r$
    - **Flat Top**: 
        - $x = size \cdot \frac{3}{2} \cdot q$
        - $y = size \cdot \sqrt{3} \cdot (r + q/2)$
    - *Note*: `size` is the radius to a vertex ($vertex\_dist = spacing / \sqrt{3}$).

- **Pixel-to-Axial Transformation**:
    - Inverse of the above matrices. Used for coordinate lookups and snapping.

- **Hex Rounding (Cube Rounding)**:
    1. Convert axial $(q, r)$ to cube $(x, y, z)$ where $x = q, z = r, y = -x-z$.
    2. Round $x, y, z$ to the nearest integers $rx, ry, rz$.
    3. Calculate differences $dx, dy, dz$.
    4. Adjust the coordinate with the largest difference to satisfy $rx+ry+rz=0$.
    5. Convert back to axial.

### 3. Backend Implementation
- **MapGridLayer**: Updated to render hexagonal wireframes using `cv2.polylines`.
- **TokenFilter**: Implements `_apply_hex_snapping` using the shared geometry utility.
- **VisibilityEngine**:
    - **Plane-Based Boundary Test**: For each PC token cell, calculate 6 linear equations ($ax + by + c \le 0$).
    - **Normals for Pointy Top**: $(\pm 1, 0), (\pm 0.5, \pm \frac{\sqrt{3}}{2})$.
    - **Same-Side BFS**: During `_calculate_token_footprint`, each pixel is tested against these planes before being added.
    - **Numba Update**: `_numba_bfs_flood_fill` will be updated to receive the plane coefficients and perform the same-side check in the hot loop.

### 4. Frontend Implementation
- **GridLayer.tsx**:
    - Updated to render a hexagonal mesh using SVG `<path>` elements to minimize DOM nodes.
    - Interaction: Dragging the origin handle stays simple. Dragging the scale handle calculates the new `spacing_svg` based on the distance from the origin to the current pointer position relative to the grid orientation.
- **SettingsModal.tsx**:
    - Added a "Grid Type" dropdown in the "Grid & Map" tab.

## Success Criteria
- [ ] Users can toggle between Square, Hex (Pointy), and Hex (Flat) in the map configuration.
- [ ] The grid layer correctly renders the selected hexagonal geometry in both the projector and the web UI.
- [ ] Tokens snap precisely to the center of hexagonal cells.
- [ ] PC visibility correctly fills the hexagonal cell and is clipped by adjacent walls.
