# Layered Composition Renderer Design

## Overview

This document outlines the refactor of the `Renderer` from a monolithic class into a layered composition system. This architecture enhances extensibility, improves performance through surgical updates, and simplifies testing of individual visual components.

## Goals

1. **Extensibility**: Easily add new visual layers (e.g., Fog of War, Token Overlays) without modifying the core renderer logic.
1. **Performance**: Minimize CPU/GPU usage by re-rendering and re-compositing only the modified rectangular regions (patches) of the screen.
1. **Testability**: Enable isolated unit testing of individual layers and the composition logic itself.
1. **Composition**: Support varied blending modes and complex visual stacks.

## Core Components

### 1. `Renderer` (Coordinator)

The central manager of the rendering pipeline.

- Maintains a dynamic stack (list) of `Layer` objects.
- Orchestrates the frame generation by collecting `ImagePatch`es from each layer.
- Performs the final composition onto the output buffer based on `LayerMode`.
- **Cache Invalidation**: Automatically invalidates the composite frame if the layer stack itself changes (e.g., during scene transitions).

### 2. `Layer` (Interface)

An abstract base class for all visual components.

- **`render(current_time: float) -> list[ImagePatch]`**: Inspects the state and returns patches to be drawn.
- **`is_dirty: bool`**: Property that determines if the layer needs a redraw based on `WorldState` timestamps.
- **`layer_mode: LayerMode`**: Defines how the layer's output interacts with layers below it.
- **Caching**: Each layer tracks its own `_last_state_timestamp` to decide if it can reuse previously generated patches.

## Standard Layer Stack (Bottom to Top)

1. **`MapLayer`**: Renders the background map (SVG/Image).
1. **`FogOfWarLayer`**: Renders the explored/unexplored mask.
1. **`VisibilityLayer`**: Renders real-time line-of-sight highlights.
1. **`SceneLayer` / `LegacySceneLayer`**: Renders the active scene's content (e.g., calibration patterns).
1. **`HandMaskLayer`**: Renders the "digital shadow" to protect hand tracking.
1. **`MenuLayer`**: Renders the interactive menu system.
1. **`TokenLayer`**: Renders ghost tokens and labels.
1. **`NotificationLayer`**: Renders system-level alerts.
1. **`DebugLayer`**: Renders FPS and diagnostic info.
1. **`CursorLayer`**: Renders the virtual pointer/reticle.

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

1. **Request Patches**: The `Renderer` iterates through the active layer stack from bottom to top.
1. **Stale Check**: Each layer compares the relevant `WorldState` timestamp with its `last_rendered_timestamp`.
   - If `state_timestamp > last_rendered_timestamp`, the layer re-renders its patches and updates its cache.
   - Otherwise, it returns the cached patches.
1. **Composition**:
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
