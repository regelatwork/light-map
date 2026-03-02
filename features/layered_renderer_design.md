# Layered Composition Renderer Design

## Overview
This document outlines the refactor of the `Renderer` from a monolithic class into a layered composition system. This architecture enhances extensibility, improves performance through surgical updates, and simplifies testing of individual visual components.

## Goals
1.  **Extensibility**: Easily add new visual layers (e.g., Fog of War, Token Overlays) without modifying the core renderer logic.
2.  **Performance**: Minimize CPU/GPU usage by re-rendering and re-compositing only the modified rectangular regions (patches) of the screen.
3.  **Testability**: Enable isolated unit testing of individual layers and the composition logic itself.
4.  **Composition**: Support varied blending modes and complex visual stacks.

## Core Components

### 1. `Renderer` (Coordinator)
The central manager of the rendering pipeline.
- Maintains a dynamic stack (list) of `Layer` objects.
- Orchestrates the frame generation by collecting `ImagePatch`es from each layer.
- Performs the final composition onto the output buffer based on `LayerMode`.

### 2. `Layer` (Interface)
An abstract base class for all visual components.
- **`render(state: WorldState) -> list[ImagePatch]`**: Inspects the state and returns patches to be drawn.
- **`layer_mode: LayerMode`**: Defines how the layer's output interacts with layers below it.
- **Caching**: Each layer tracks a `last_rendered_timestamp` to decide if it can reuse previously generated patches.

### 3. `ImagePatch` (Data Structure)
Represents a rectangular region of pixels.
- `x, y, width, height`: Position and size in screen coordinates.
- `data`: `np.ndarray` (RGBA) containing the pixel data.

### 4. `LayerMode` (Enum)
- `NORMAL`: Standard alpha blending (Source Over). The patch's alpha channel determines transparency.
- `BLOCKING`: The patch completely replaces the underlying pixels. This is a high-performance mode for opaque backgrounds or full-screen UI elements.

## Data Flow & State Tracking

### WorldState Timestamps
The `WorldState` serves as the single source of truth and maintains monotonic timestamps (or version IDs) for its components:
- `map_timestamp`
- `menu_timestamp`
- `calibration_timestamp`
- `tokens_timestamp`

### Rendering Pipeline
1.  **Request Patches**: The `Renderer` iterates through the active layer stack from bottom to top.
2.  **Stale Check**: Each layer compares the relevant `WorldState` timestamp with its `last_rendered_timestamp`.
    - If `state_timestamp > last_rendered_timestamp`, the layer re-renders its patches and updates its cache.
    - Otherwise, it returns the cached patches.
3.  **Composition**:
    - If `LayerMode.BLOCKING`, the `Renderer` performs a fast `numpy` slice assignment.
    - If `LayerMode.NORMAL`, the `Renderer` performs alpha blending for the patch area.

## Performance Optimizations
- **Surgical Redraws**: By returning a `list[ImagePatch]`, a layer like the `MenuLayer` only triggers updates for the specific rectangles occupied by buttons, leaving the rest of the frame untouched.
- **Alpha Shortcut**: Layers can skip generating an alpha channel for `BLOCKING` patches to save memory bandwidth.
- **Static Backgrounds**: The complex SVG map layer only re-rasterizes when the map pans, zooms, or the configuration changes, remaining purely cached during menu interactions.

## Testing Strategy
- **Layer Isolation**: Mock `WorldState` with specific timestamps to verify that layers re-render only when necessary and produce correct patch coordinates.
- **Composition Verification**: Use 2x2 pixel test layers with known colors and alpha values to verify the `Renderer`'s `NORMAL` and `BLOCKING` logic.
- **Integration Tests**: Verify that changing a value in `WorldState` correctly propagates through the layers to the final output frame.
