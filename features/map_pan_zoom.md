# Map Pan and Zoom Editor Design

This document outlines the design for the **Map Pan and Zoom Editor**, a visual tool for calibrating the projector's viewport relative to the map. This tool provides a "What You See Is What You Get" (WYSIWYG) interface for positioning and scaling the map's visible area.

## Goals

1. **Visual Calibration**: Provide a clear visual representation of the projector's "window" (viewport) on the map.
2. **Precise Panning**: Enable grid-aligned panning to ensure the map aligns perfectly with the physical projector bounds.
3. **Intuitive Zooming**: Allow zooming by dragging the viewport edges, pinning the opposite side to maintain context.
4. **Mutual Exclusion**: Ensure the interface remains clean by toggling between Grid and Viewport calibration modes.

## Core Concepts

- **Viewport Rectangle**: A visual overlay representing the projector's current resolution (`proj_res`) and aspect ratio. The rectangle is centered at the map's current `(x, y)` coordinates, and its world-space dimensions are inversely proportional to the `zoom` level.
- **Opposite-Side Fixed Zoom**: When resizing the viewport, the midpoint of the edge opposite to the one being dragged remains stationary on the map. This allows for precise scaling relative to a fixed map feature.
- **Grid Snapping**: Panning the viewport snaps the center point to 1-grid-unit increments (based on `grid_spacing_svg`) to facilitate perfect alignment with the physical grid.
- **Backend Synchronization**: The tool communicates with the backend via the `SET_VIEWPORT` action. To ensure consistency, the frontend and backend both use a unified `(x, y)` coordinate system for the viewport center, resolving previous naming inconsistencies (e.g., `pan_x`).

## UI Workflow

### Interaction Model: Viewport Calibration

1. **Toggle Mode**: In the "Entity Properties" sidebar, the user can toggle between **Visual Grid Editor** and **Map Pan & Zoom**. Only one mode can be active at a time.
2. **Pan (Center Handle)**:
    - A green handle at the center of the viewport rectangle allows for panning.
    - Dragging the handle moves the entire viewport.
    - Movement snaps to the nearest grid intersection.
3. **Zoom (Side Handles)**:
    - Handles at the midpoints of the Top, Bottom, Left, and Right edges allow for resizing.
    - Dragging a handle scales the rectangle while keeping the opposite side's midpoint fixed.
    - The aspect ratio is strictly maintained during resizing.
4. **Reset Zoom**: A "Reset to 1:1" button in the sidebar immediately sets the zoom factor to 1.0.

### Visual Feedback

- **Viewport Overlay**: Rendered as a dashed blue outline with a semi-transparent fill.
- **Active Handles**: High-contrast circles (Green for Pan, Blue for Zoom) appear only when the mode is active.
- **Coordinates & Zoom**: Real-time feedback of the viewport's X, Y, and Zoom values is displayed in the sidebar.

## Implementation Principles

- **CalibrationContext**: A shared React context manages the `activeMode` (`NONE`, `GRID`, or `VIEWPORT`).
- **ViewportEditLayer**: A dedicated SVG layer handles the rendering and mouse interactions for the viewport rectangle.
- **Backend Sync**: Final viewport parameters are sent to the backend via `SET_VIEWPORT` and persisted in the map's session configuration.
