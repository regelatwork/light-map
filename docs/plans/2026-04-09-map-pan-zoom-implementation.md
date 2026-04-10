# Implementation Plan: Map Pan and Zoom Editor

This plan details the steps required to implement the **Map Pan and Zoom Editor** in the frontend, including state management, UI components, and backend integration.

## 0. Technical Prerequisites & Core Corrections

### Fix Backend Naming Inconsistency
The backend currently uses `pan_x` and `pan_y` in some places but expects `x` and `y` elsewhere. We will unify this.
- **Action Required**: Update `src/light_map/action_dispatcher.py`'s `handle_set_viewport` to align its payload keys with the `MapState` and frontend `SystemState` (using `x` and `y`).

### Coordinate System Awareness
- **Screen Space**: Browser window coordinates (from mouse events).
- **World Space**: Map/SVG coordinates.
- **Crucial**: Always use `screenToWorld` from `CanvasContext` to convert mouse positions before calculating offsets or distances.

## 1. State Management & Mutual Exclusion

### Evolve `GridEditContext` to `CalibrationContext`
- Rename `frontend/src/components/GridEditContext.tsx` to `CalibrationContext.tsx`.
- Replace `isGridEditMode: boolean` with `activeMode: 'NONE' | 'GRID' | 'VIEWPORT'`.
- Add `setMode(mode: 'NONE' | 'GRID' | 'VIEWPORT')` to the context.
- **Comprehensive Refactor**: Update ALL consumers of `useGridEdit`:
  - `ConfigurationSidebar.tsx`
  - `GridLayer.tsx`
  - `SettingsModal.tsx`
  - All related `.test.tsx` files.

## 2. UI Components (Sidebar)

### Update `ConfigurationSidebar.tsx`
- Add a new section "Map Pan & Zoom" below the "Visual Grid Editor" section.
- Implement a toggle button for `VIEWPORT` mode that disables `GRID` mode if active.
- Show current `viewport.x`, `viewport.y`, and `viewport.zoom` from `SystemState` as read-only or editable inputs.
- Add a "Reset to 1:1" button that triggers a `SET_VIEWPORT` action with `zoom: 1.0`.

## 3. Viewport Visualization Layer

### Create `ViewportEditLayer.tsx`
- **Resolution Access**: Use `config.proj_res[0]` for width and `config.proj_res[1]` for height (not `.x`/.`.y`).
- **Render Logic**:
  - Only render when `activeMode === 'VIEWPORT'`.
  - Calculate the viewport rectangle's dimensions: `w = config.proj_res[0] / zoom`, `h = config.proj_res[1] / zoom`.
  - Position the rectangle: it is centered at `(viewport.x, viewport.y)`. 
  - Bounds are: `x_min = viewport.x - w/2`, `y_min = viewport.y - h/2`, etc.

- **Center Handle (Pan)**:
  - Render a green handle at the rectangle's center `(viewport.x, viewport.y)`.
  - Implement `onMouseDown` to start panning.
  - Snap movement to `grid_spacing_svg` during `onMouseMove`.

- **Side Handles (Zoom - "Opposite Side Fixed")**:
  - **Logic Example (Top Handle)**:
    - **Fixed Point (P_fixed)**: The Bottom-Center of the rectangle: `(viewport.x, viewport.y + h/2)`.
    - **Interactive Point (P_top)**: The current mouse position in world space.
    - **New Height (H_new)**: `Distance between P_top.y and P_fixed.y`.
    - **New Zoom**: `config.proj_res[1] / H_new`.
    - **New Center Y**: `P_fixed.y - H_new / 2`.
    - **New Center X**: `viewport.x` (remains aligned with center unless side-dragged).
    - **Maintain Aspect Ratio**: The width must be scaled by the same zoom factor automatically.

## 4. Canvas Integration

### Update `SchematicCanvas.tsx`
- Add `<ViewportEditLayer />` to the SVG hierarchy.
- Ensure the layer is correctly transformed by the current rotation and viewbox.

## 5. API & Backend Integration

### Update `services/api.ts`
- Add `setViewportConfig(x: number, y: number, zoom: number, rotation: number)` function.
- Payload MUST use keys `x` and `y` (not `pan_x`, `pan_y`) to match the fixed backend handler.

## 6. Verification Plan

### Automated Tests
1. **Unit Tests (Vitest)**:
   - `CalibrationContext.test.tsx`: Test mode switching logic.
   - `ViewportEditLayer.test.tsx`: Test "Opposite Side Fixed" math for all four handles.
2. **E2E Tests (Playwright)**:
   - `viewport_calibration.spec.ts`: Test the full workflow: toggle mode -> pan (snap) -> zoom -> verify sidebar values.

### Manual Verification
- Load a map, enter Viewport mode, and verify that the projected viewport matches the visual rectangle.
- Verify that "Reset to 1:1" works correctly.
- Ensure state persists after a page reload.
