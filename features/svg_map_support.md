# Feature: SVG Map Support

## Overview
This feature allows the system to load an SVG file (e.g., a floor plan, museum map, or artistic design) and project it onto the calibrated surface. The map should be correctly scaled to the projector's resolution and could potentially support interactive elements in the future.

## Goals
1.  **High-Quality Rendering**: Support vector-based maps for crisp projection at any resolution.
2.  **Layered Display**: Show the map as a background layer behind the menu system.
3.  **Real-World Scale**: Calibrate zoom level to achieve 1:1 mapping (e.g., 1 inch on map = 1 inch on surface).
4.  **Navigation Controls**:
    *   **Pan**: Move the map view.
    *   **Zoom**: Scale in/out.
    *   **Rotate**: 90-degree increments.
    *   **Restore**: Quickly return to saved viewpoints.

## Detailed Interaction Design

### 1. Map Control Mode
To prevent conflict with menu navigation, we introduce a **Map Control Mode**.
*   **Entry**: Select "Map Controls" from the main menu.
*   **Exit**: Perform "Summon Menu" (Victory) gesture or hit an on-screen "Exit" button.

### 2. Gestures & Controls
*   **Pan (Move)**:
    *   **Gesture**: **Closed Fist** (Grab).
    *   **Action**: While holding "Closed Fist", moving the hand drags the map (1:1 movement).
    *   **Release**: Open hand to stop panning.
*   **Zoom**:
    *   **Gesture**: **Two-Hand Pointing** (Index fingers extended on both hands).
    *   **Action**:
        1.  **Detect**: System sees two "Pointing" hands.
        2.  **Debounce**: Hold gesture for `ZOOM_DELAY` (e.g., 0.5s).
        3.  **Engage**: Visual indicator appears between hands.
        4.  **Scale**: Moving hands apart zooms IN; moving together zooms OUT.
    *   **Feedback**:
        *   **Zoom Level**: Display current scale (e.g., "150%") and "1:1" marker.
        *   **Grid**: A temporary 1-inch grid overlay appears while zooming to assist with scale.
*   **Rotate**:
    *   **Controls**: On-screen **[⟳]** (CW) and **[⟲]** (CCW) buttons.
    *   **Action**: Rotates map 90 degrees around the center of the screen.

## Grid & Scale Calibration Process

To achieve "1 inch on screen = 1 inch in reality", we need to know the **Projector Pixels Per Inch (PPI)**.

### Step A: Printed Target Calibration
Instead of manual measurement, we use a pre-printed calibration target.

1.  **Generate Target**:
    *   Create a script `generate_calibration_target.py` to produce a PDF/SVG.
    *   **Content**: Two distinct markers (e.g., ArUco or specific shapes) separated by a known distance (e.g., 100mm).
    *   **Instruction**: User prints this target at 100% scale.

2.  **Calibration Sequence**:
    *   **User Action**: Select "Calibrate Scale" from the menu.
    *   **Instruction**: "Place the printed target on the surface."
    *   **Detection**: The camera detects the markers and calculates the distance in **camera pixels**.
    *   **Mapping**: Using the existing `projector_calibration.npz` (Camera -> Projector homography), we transform the marker positions to **projector pixels**.
    *   **Calculation**:
        *   `Distance_Projector_Px = dist(Marker1_Proj, Marker2_Proj)`
        *   `PPI = Distance_Projector_Px / (Known_Distance_mm / 25.4)`

3.  **Confirmation & Verification**:
    *   **Action**: Once PPI is calculated, the system projects a **1-inch grid** overlaying the entire surface.
    *   **User Action**: Verify the projected grid matches the physical target or a ruler.
    *   **Confirm**: User performs a "Thumb Up" or "Victory" gesture to save the PPI and finish.
    *   **Cancel**: User exits the mode or performs "Open Palm" to retry.

### Step B: SVG Scale Factor
*   **Definition**: We must define what "1 unit" in the SVG file represents.
*   **Convention**: Default to standard **96 DPI** (common SVG default).
    *   If the SVG grid line is 96 units long, it represents 1 inch.
*   **Calculation**:
    *   To render at 1:1 scale: `Scale_Factor = Projector_PPI / SVG_DPI`.

## Data Storage & Persistence

To ensure calibration and map states persist across sessions, we will use a JSON-based storage system.

### 1. Storage Location
*   **File**: `map_state.json` in the project root.
*   **Format**: Human-readable JSON.

### 2. Schema Design
```json
{
  "global": {
    "projector_ppi": 96.0,
    "last_used_map": "museum_floor.svg"
  },
  "maps": {
    "museum_floor.svg": {
      "scale_factor": 1.0,
      "viewport": {
        "x": 150,
        "y": 200,
        "zoom": 1.5,
        "rotation": 90
      },
      "bookmarks": [
        {"name": "Room 101", "x": 10, "y": 20, "zoom": 1.0, "rotation": 0}
      ]
    }
  }
}
```

### 3. Usage Pattern
*   **On App Start**: Load `projector_ppi` from `global`.
*   **On Map Load**: 
    1. Check if the SVG filename exists in the `maps` dictionary.
    2. If it exists, restore the `viewport` (x, y, zoom, rotation).
    3. If not, initialize with default values (centered at 1:1 scale).
*   **On Change**: Update the in-memory state and save to `map_state.json` periodically or on app exit.

## Implementation Plan

### Phase 1: SVG Loading & Rendering (The Foundation)
*   **Goal**: Load an SVG file and render it to a static `np.ndarray` (BGR image) at a specific resolution.
*   **Milestone**: `tests/test_svg_loader.py` passes.
*   **Files**:
    *   `src/light_map/svg_loader.py` (New): `SVGLoader` class.
    *   `tests/test_svg_loader.py` (New): Unit tests.
*   **Tests**:
    *   `test_load_valid_svg`: Ensure file loads.
    *   `test_render_dimensions`: Verify output image matches requested WxH.
    *   `test_parse_paths`: Check if `svgelements` extracts paths correctly.

### Phase 2: Viewport & State Management (The Logic)
*   **Goal**: Manage Pan/Zoom/Rotation state and apply affine transformations. Implement `MapSystem`.
*   **Milestone**: `tests/test_map_system.py` passes.
*   **Files**:
    *   `src/light_map/map_system.py` (New): `MapSystem` class with `viewport` state.
    *   `tests/test_map_system.py` (New): Unit tests.
*   **Tests**:
    *   `test_pan`: Verify (x, y) updates.
    *   `test_zoom`: Verify scale updates.
    *   `test_transform_point`: Check if a point (10,10) transforms correctly under zoom/pan.

### Phase 3: Integration & Rendering (The Visuals)
*   **Goal**: Integrate `MapSystem` into `InteractiveApp` and update `Renderer` to draw the map layer.
*   **Milestone**: `InteractiveApp` renders the map background.
*   **Files**:
    *   `src/light_map/renderer.py`: Update `render()` to accept a background image.
    *   `src/light_map/interactive_app.py`: Initialize `MapSystem` and composite layers.
    *   `tests/test_renderer.py`: Update to test layered rendering.
*   **Tests**:
    *   `test_render_with_background`: Ensure map is drawn behind menu.

### Phase 4: Interaction & Gestures (The Control)
*   **Goal**: Implement "Map Mode", Pan/Zoom gestures, and on-screen controls.
*   **Milestone**: `tests/test_interactive_app.py` passes with new gestures.
*   **Files**:
    *   `src/light_map/gestures.py`: Add "Two-Hand Pointing" detection.
    *   `src/light_map/interactive_app.py`: Handle state transitions (Menu <-> Map).
    *   `src/light_map/input_manager.py`: Add gesture debounce logic.
*   **Tests**:
    *   `test_enter_map_mode`: Verify mode switch.
    *   `test_two_hand_zoom`: Verify zoom level changes with hand distance.

### Phase 5: Calibration & Persistence (The Polish)
*   **Goal**: Implement PPI calibration, grid verification, and JSON storage.
*   **Milestone**: App saves/loads state from `map_state.json`.
*   **Files**:
    *   `src/light_map/map_config.py` (New): Persistence logic.
    *   `src/light_map/calibration_logic.py`: Add PPI calibration routine.
*   **Tests**:
    *   `test_save_load_state`: Verify JSON I/O.
    *   `test_ppi_calculation`: Check formula correctness.

## Brainstorming & Requirements

### 1. Library Selection
We need a Python library to handle SVG files. Candidates:
*   **`svgelements`**: Excellent for parsing and manipulating SVG paths. Lightweight and pure Python.
*   **`CairoSVG`**: Powerful rasterizer, but requires `libcairo` system dependency (might be tricky on some RPi setups).
*   **`svglib`**: Good for basic conversion to ReportLab objects, then to images.

**Recommendation**: Start with `svgelements` for parsing paths if we want to draw them ourselves with OpenCV (fast, low dependencies), or `CairoSVG` if we need full CSS/gradient support.

### 2. Implementation Layers

#### Data Layer (`SVGLoader`)
*   Load `.svg` file.
*   Extract viewport/viewbox.
*   Scale all paths/elements to fit the `AppConfig` width/height.

#### Logic Layer (`MapSystem`)
*   Manage the current "active" map.
*   **Viewport State**: (x, y, zoom_level, rotation).
*   **Transformations**: Apply affine transformations to map coordinates before rendering.

#### Rendering Layer (`Renderer` Update)
*   The `Renderer` should now support multiple layers:
    1.  **Background**: SVG Map (Transformed).
    2.  **Middle**: Menu System.
    3.  **Foreground**: Hand Landmarks / Debug Cursor.