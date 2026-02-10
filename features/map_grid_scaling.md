# Map Grid Scaling & Alignment Design

This document outlines the design for implementing real-world scale (1:1) mapping for SVG maps, allowing the projected map to align with physical grids (e.g., 1-inch squares).

## Goals

1.  **Automated Grid Detection**: Automatically identify the primary grid spacing within an SVG map file (e.g., "50 units").
2.  **Manual Calibration (Visual Alignment)**: Allow the user to manually scale the map to align its internal grid with a projected, calibrated reference grid (the "markers").
3.  **Real-World Scale Persistence**: Store the scale factor required to achieve 1:1 projection for each map.

## Core Concepts

*   **PPI (Projector Pixels Per Inch)**: A global constant derived from `projector_calibration.py` (ArUco markers). It tells us how many pixels span 1 physical inch.
*   **SVG Unit**: The internal coordinate system of the SVG file (unitless, px, cm, etc.).
*   **Map Scale Factor ($S$)**: The zoom level applied during rendering.
    *   $S = \frac{	ext{Projector Pixels}}{	ext{SVG Units}}$
*   **Target Scale ($S_{1:1}$)**: The specific zoom level where 1 SVG Grid Unit equals 1 Physical Grid Unit.
    *   $S_{1:1} = \frac{	ext{Physical Size (Inches)} 	imes 	ext{PPI}}{	ext{SVG Grid Spacing (Units)}}$

## Feature 1: Automated Grid Detection

### Algorithm
The `SVGLoader` will analyze the geometry of the loaded map to infer grid lines.

1.  **Extraction**: Iterate through all `Line`, `Path` (linear segments), `Rect`, and `Polyline` elements.
2.  **Normalization**: Convert all segments to absolute coordinates.
3.  **Filtering**: Ignore short lines (noise/details) and non-axis-aligned lines (diagonal walls).
4.  **Clustering**:
    *   Group vertical lines by their X-coordinate.
    *   Group horizontal lines by their Y-coordinate.
5.  **Spacing Analysis**:
    *   Calculate the distance (gap) between adjacent unique coordinates in each group.
    *   Compute a histogram of these gaps.
    *   The **mode** (most frequent gap) is the candidate grid size ($G_{svg}$).
6.  **Validation**:
    *   Require a minimum number of repeating lines (e.g., > 3) to confirm a grid.
    *   Check if horizontal and vertical spacings match (square grid) or differ (rectangular).

### Algorithm B: Raster Analysis (Fallback)
If the SVG contains large embedded images or the vector analysis fails to find a consistent grid, the system analyzes the rendered image.

1.  **Rendering**: Render the SVG to a high-resolution buffer (e.g., 2048px wide).
2.  **Edge Detection**: Apply Canny edge detector to highlight lines.
3.  **Hough Line Transform**: Use `cv2.HoughLinesP` to detect straight lines.
4.  **Filtering**: Keep only long horizontal and vertical lines.
5.  **Frequency Analysis (Optional)**:
    *   Collapse the edge image into 1D profiles (sum of rows, sum of columns).
    *   Apply FFT (Fast Fourier Transform) or autocorrelation to find the dominant spatial frequency (periodicity).
    *   The peak frequency corresponds to the grid spacing.
6.  **Spacing Extraction**: Similar to Algorithm A, calculate gaps between detected lines or use the FFT peak.

### Strategy Selection
1.  **Attempt Algorithm A (Vector)**: Fast and precise for vector grids.
2.  **If A fails (low confidence)**:
    *   Check if SVG contains `<image>` elements covering a significant area.
    *   If yes, **Attempt Algorithm B (Raster)**.
3.  **Result Integration**:
    *   If both return results, prefer A (infinite precision).
    *   If only B returns results, use B but with a "Medium" confidence flag.

### Output
*   `detected_grid_spacing_x`: float (SVG Units)
*   `detected_grid_spacing_y`: float (SVG Units)
*   `confidence`: float (0.0 - 1.0)

## Feature 2: Manual Scale Alignment (The "Markers")

Since automated detection might fail or the physical size of the grid is unknown (e.g., "Is this 5ft or 1 meter?"), a manual alignment mode is required.

### UI Workflow
1.  **Enter Scale Mode**: User selects "Calibrate Map Scale" from the menu.
2.  **Project Reference Crosshairs**: The system overlays **green crosshairs with a black outline** (for high contrast on light/dark maps) representing a known physical size (e.g., 1 inch intervals) based on the global PPI.
    *   *Note*: This requires the global PPI to be calibrated first.
3.  **User Adjustment**:
    *   **Zoom**: Adjust map scale until map grid lines match the spacing of the projected crosshairs.
    *   **Offset**: Pan the map to align a specific grid intersection with the center crosshair. This establishes the grid origin.
    *   **Interaction**:
        *   "Zoom to Fit": Adjusts map scale.
        *   "Pan to Align": Adjusts map offset (origin).
        *   "Define Unit": Cycle through reference grid sizes (1 inch, 5 feet, 1 meter).
4.  **Confirm**: User performs a confirmation gesture (e.g., Victory).
5.  **Calculation**:
    *   The system captures the current zoom level ($S_{current}$) and offset ($O_{grid}$).
    *   It calculates the relationship: "1 Grid Unit = $X$ Inches".
    *   *Future Utility*: This alignment allows the system to treat the grid as a source of discrete positions (snapping).

## Implementation Plan

### Phase 1: Logic & Data Structures
*   Update `MapEntry` in `map_config.py` to store:
    *   `grid_spacing_svg`: float (Detected or Manual)
    *   `grid_origin_svg`: tuple (x, y) (Manual Offset)
    *   `physical_unit_inches`: float (e.g., 1.0 for inches, 60.0 for 5ft)
    *   `scale_factor_1to1`: float (Calculated)
*   Implement `detect_grid_spacing` in `svg_loader.py`.

### Phase 2: UI & Interaction
*   Add `MapSystem.set_scale_to_grid(physical_size_inches)` method.
*   Implement `_draw_scale_overlay` in `interactive_app.py`:
    *   Draws calibrated PPI crosshairs (Green with Black outline).
    *   Draws the current map (Background).
    *   Displays text: "Align Map Grid to Crosshairs".

### Phase 3: Integration
*   Add menu item "Map Settings > Set Scale".
*   Auto-run detection when loading a new map.
*   If confidence is high, toast message: "Grid Detected: 50px. Set as 1 inch?"
