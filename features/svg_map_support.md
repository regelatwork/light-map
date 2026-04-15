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
  - **Token Toggle**: `Map Settings` menu item.
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

## Technical Design & Pitfalls

### 1. Matrix Multiplication Order
The `svgelements` library follows a specific matrix multiplication convention: `A * B` means **Apply A then B**. 
To match standard SVG nested transformations (where inner transforms are applied before parent transforms), the matrices must be composed as:
`TotalTransform = InnerTransform * ParentTransform * RootViewportMatrix`

Failure to follow this order results in incorrect translation offsets and "warped" scaling when elements are nested in groups.

### 2. Transformation Reification
During parsing (`svgelements.SVG.parse()`), the library behaves inconsistently across element types:
- **Shapes (Rect, Circle, Path)**: Reified into **absolute root coordinates**. Their `.transform` property is often `Identity` because the transform has already been baked into the path segments.
- **Images & Text**: Retain **local coordinates** and cumulative `.transform` properties.

**Developer Pitfall**: Manual tree traversal must account for this. If you manually accumulate transforms for shapes, you will likely **double-scale** the elements. The safest approach is to use the reified coordinates and apply only the root-to-screen viewport matrix.

### 3. Gradient Resolution & Chained Hrefs
Inkscape often chains gradients using `xlink:href` (e.g., a `radialGradient` inheriting stops from a `linearGradient`).
- **Lookup**: Always use an `id_map` for gradient lookup. `svgelements.get_element_by_id` can be unreliable for elements nested deeply in `<defs>`.
- **Recursion**: `get_gradient_stops` must recursively resolve `xlink:href` to capture stops from the parent gradient.
- **Empty Group Bug**: In Python, an `svgelements.Group` (which gradients often are) evaluates to `False` if it has no direct children. Always use `if element is not None` instead of `if element` when checking for retrieved gradients.

### 4. Gradient Units & Coordinates
- **objectBoundingBox**: Coordinates are 0.0 to 1.0 relative to the element's bounding box.
- **userSpaceOnUse**: Coordinates are absolute SVG units (often mm in Inkscape, converted to px by the parser).
- **Percentages**: Must be resolved relative to the correct reference (the element's bbox for `objectBoundingBox` or the SVG viewport for `userSpaceOnUse`).

### 5. Masking pass
Masks are applied by rendering the mask's subtree into a temporary grayscale buffer. The luminance of this buffer is then multiplied by the alpha channel of the target element's buffer before blending into the final image. Ensure the mask is rendered using the same root viewport matrix as the element to maintain alignment.

## Implementation Status

- [x] **Phase 1: SVG Loading & Rendering**: Support for paths, fills, and Base64 raster images.
- [x] **Phase 2: Viewport & State Management**: Persistent `MapSystem` logic.
- [x] **Phase 3: Integration & Rendering**: Unconditional map background with Dark Theme.
- [x] **Phase 4: Interaction & Gestures**: Open Palm pan, Two-Hand Pointing zoom, and Victory exit.
- [x] **Phase 5: Calibration & Persistence**: ArUco-based PPI calibration and JSON storage.
