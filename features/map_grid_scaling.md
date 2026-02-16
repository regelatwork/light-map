# Map Grid Scaling & Alignment Design

This document outlines the design for implementing real-world scale (1:1) mapping for SVG maps, allowing the projected map to align with physical grids (e.g., 1-inch squares).

## Goals

1. **Automated Grid Detection**: Automatically identify the primary grid spacing within an SVG map file (e.g., "50 units").
1. **Manual Calibration (Visual Alignment)**: Allow the user to manually scale the map to align its internal grid with a projected, calibrated reference grid (the "markers").
1. **Real-World Scale Persistence**: Store the scale factor required to achieve 1:1 projection for each map.

## Core Concepts

- **PPI (Projector Pixels Per Inch)**: A global constant derived from `projector_calibration.py` (ArUco markers). It tells us how many pixels span 1 physical inch.
- **SVG Unit**: The internal coordinate system of the SVG file (unitless, px, cm, etc.).
- **Map Scale Factor ($S$)**: The zoom level applied during rendering.
  - $S = \\frac{\\text{Projector Pixels}}{\\text{SVG Units}}$
- **Target Scale ($S\_{1:1}$)**: The specific zoom level where 1 SVG Grid Unit equals 1 Physical Grid Unit.
  - $S\_{1:1} = \\frac{\\text{Physical Size (Inches)} \\times \\text{PPI}}{\\text{SVG Grid Spacing (Units)}}$
- **User Zoom**: The relative zoom level applied by the user during navigation.
  - $\\text{Total Zoom} = S\_{1:1} \\times \\text{User Zoom}$

## Feature 1: Automated Grid Detection

### Algorithm A: Vector Analysis

The `SVGLoader` analyzes the geometry of the loaded map to infer grid lines.

1. **Extraction**: Iterate through all `Line`, `Path` (linear segments), `Rect`, and `Polyline` elements.
1. **Clustering**: Group lines by axis alignment.
1. **Spacing Analysis**: Calculate gaps between unique coordinates and find the mode.
1. **Validation**: Requires > 3 repeating lines.

### Algorithm B: Raster Analysis (Fallback)

If vector analysis fails (e.g., map is an embedded image), the system falls back to signal processing on the rendered image.

1. **Rendering**: Render the SVG to a high-resolution buffer (2048px wide).
1. **Edge Detection**: Apply Canny edge detector.
1. **Autocorrelation**: Collapse the edge map into 1D profiles (sum of rows/cols) and calculate the autocorrelation to find the dominant spatial frequency (grid spacing).

## Feature 2: Manual Scale Alignment

Since automated detection might fail or the physical size of the grid is unknown, a manual alignment mode is provided.

### UI Workflow

**Interaction Model: Anchor and Scale**
To align the projected grid with the map image:
1.  **Anchor**: Use the **Pan** gesture (Closed Fist) to move the grid overlay. Align the **Grid Origin** (highlighted with a green circle and black outline) with a known intersection or feature on the map.
2.  **Scale**: Use the **Zoom** gesture (Two Pointing Hands) to adjust the grid spacing. The zoom is **centered on the Grid Origin**, meaning the anchor point remains fixed while the rest of the grid expands or contracts around it. This prevents the "drifting" issue common with center-of-screen or center-of-hands zooming during calibration.

**Visual Feedback**
- **Grid Lines**: Rendered as high-contrast crosses at intersections (Green with Black outline).
- **Grid Origin**: Distinctly highlighted with a green circle and black outline to indicate the pivot point.
- **Initialization**: The grid origin defaults to the center of the screen upon entering calibration mode.

## Feature 3: Interaction Refinements

- **Fixed Pivot Zoom**: Zoom interactions now scale the map around the center of the screen, regardless of where the hands are located. This prevents the map from "jumping" and makes alignment easier.
- **Rotation Handling**: Coordinate transformations (`screen_to_world`) now correctly account for map rotation (90/180/270 degrees).
- **Zoom 1:1**: A new menu item "Zoom 1:1" resets the user's zoom level to exactly match the calibrated base scale, without changing Pan or Rotation.
- **Reset View**: Resets Pan/Rotation and sets Zoom to the calibrated base scale (1:1).

## Implementation Details

- **`MapConfig`**: updated to store `grid_spacing_svg`, `physical_unit_inches`, and `scale_factor_1to1`.
- **`MapSystem`**: updated with `set_zoom_around_pivot` and matrix-based coordinate transforms.
- **`SVGLoader`**: added `detect_grid_spacing` (Vector + Raster fallback).
- **`InteractiveApp`**: logic for state isolation, saving/restoring view, and handling new menu actions.
