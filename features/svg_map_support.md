# Feature: SVG Map Support

## Overview

This feature allows the system to load an SVG file (e.g., a floor plan, museum map, or artistic design) and project it onto the calibrated surface. The map is correctly scaled, supports interactive navigation, and persists viewport state across sessions.

## Goals

1. **High-Quality Rendering**: Support vector-based maps for crisp projection at any resolution.
1. **Layered Display**: Show the map as a background layer behind the menu system.
1. **Real-World Scale**: Calibrate zoom level to achieve 1:1 mapping (e.g., 1 inch on map = 1 inch on surface).
1. **Dark Theme & Visibility**: Use a dark palette to reduce light pollution; automatically inverts dark SVG paths to white for visibility.
1. **Navigation Controls**:
   - **Pan**: Move the map view.
   - **Zoom**: Scale in/out.
   - **Rotate**: 90-degree increments.
   - **Restore**: Automatically reload last-used viewport.

## Detailed Interaction Design

### 1. Map Control Mode

To prevent conflict with menu navigation and accidental shifts during gameplay, map manipulation is restricted to specific modes.

- **Viewing Mode (Default)**:
  - Entered automatically when a map is loaded or the menu is closed.
  - **Pan/Zoom**: Disabled.
  - **Token Toggle**: `Shaka` gesture.
  - **Summon Menu**: `Victory` gesture.
- **Map Control Mode (Interactive)**:
  - **Entry**: Select "Map Interaction Mode" from the main menu.
  - **Exit**: Hold the **Victory** gesture for 1.0 second.

### 2. Gestures & Controls (Interactive Mode)

- **Pan (Move)**:
  - **Gesture**: **Closed Fist** (Grabbing).
  - **Action**: Moving the hand translates the map in real-time ("Grabbing" the map).
- **Zoom**:
  - **Gesture**: **Two-Hand Pointing** (Index fingers extended on both hands).
  - **Action**:
    1. **Debounce**: Hold gesture for `ZOOM_DELAY` (0.5s).
    1. **Scale**: Moving hands apart zooms IN; moving together zooms OUT.
    1. **Anchor**: The map points under the fingers remain fixed ("Grabbing" behavior), allowing simultaneous Pan & Zoom.
- **Rotate**:
  - **Controls**: Menu items **Rotate CW** (90°) and **Rotate CCW** (-90°).
  - **Action**: Rotates map around the screen center.
- **Reset**:
  - **Control**: Menu item **Reset View**.
  - **Action**: Returns map to centered, 100% scale view.

## PPI Calibration Process

To achieve "1 inch on screen = 1 inch in reality", the system calculates **Projector Pixels Per Inch (PPI)**.

### ArUco Target Calibration

1. **Target**: Two ArUco markers (DICT_4X4_50, IDs 0 and 1) separated by exactly 100mm center-to-center.
1. **Detection**:
   - User selects "Calibrate Scale".
   - Camera detects markers.
   - The pixel distance between markers is transformed into projector space using the system homography.
1. **Calculation**: `PPI = Distance_Projector_Px / (100mm / 25.4)`.
1. **Verification**: A green 1-inch grid is projected. User confirms with **Victory** or retries with **Open Palm**.

## Data Storage & Persistence

Viewport and calibration data are saved to `map_state.json`.

```json
{
  "global": {
    "projector_ppi": 124.5,
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
      }
    }
  }
}
```

## Implementation Status

- [x] **Phase 1: SVG Loading & Rendering**: Support for paths, fills, and Base64 raster images.
- [x] **Phase 2: Viewport & State Management**: Persistent `MapSystem` logic.
- [x] **Phase 3: Integration & Rendering**: Unconditional map background with Dark Theme.
- [x] **Phase 4: Interaction & Gestures**: Open Palm pan, Two-Hand Pointing zoom, and Victory exit.
- [x] **Phase 5: Calibration & Persistence**: ArUco-based PPI calibration and JSON storage.
