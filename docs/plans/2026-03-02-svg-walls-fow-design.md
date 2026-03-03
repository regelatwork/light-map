# Design: SVG Wall Support and Fog of War System

**Date:** 2026-03-02  
**Status:** Validated  
**Context:** Epic `bd-8rj` (SVG Wall Support for Fog of War and Visibility)

## Overview
This system enables interactive visibility and exploration tracking for physical tabletop gaming using SVG-encoded maps. It integrates Starfinder 1e vision rules with real-time hand-gesture interactions and persistent Fog of War (FoW).

## 1. Architecture and Data Flow

### SVG Layer Extraction
The `SVGLoader` will be extended to identify visibility and movement blockers from SVG layers using case-insensitive substring matching:
- **Walls:** Layers containing "wall" (e.g., "Walls", "Wall-1"). Opaque to vision and movement.
- **Doors:** Layers containing "door". Opaque when closed; transparent when open.
- **Windows:** Layers containing "window". Vision transparent, movement blocking.
- **Unbreakable Windows:** Layers containing both "unbreakable" and "window".

### Fog of War (FoW) Persistence
- **Storage:** A bitmap (PNG) tracking "Explored" vs. "Unexplored" state will be stored at `~/.light_map/maps/[map_name]/fow.png`.
- **Resolution:** 16x the grid resolution (e.g., a 1-inch grid square = 16x16 pixels in the mask).
- **Invalidation:** The bitmap is automatically deleted if the map's grid scale or PPI changes, or via an explicit "Reset Fog of War" menu action.

## 2. Visibility and Vision Rules

### Starfinder 1e Vision Logic
- **Sources:** All tokens marked with `"type": "PC"` in `tokens.json`.
- **Sight Range:** Default of 25 grid cells (125 feet).
- **Origin Points:** For a token of size $S$, vision is calculated as the **union** of visibility polygons cast from:
  1. The center of the token.
  2. All $(S+1)^2$ grid corners occupied by the token.
- **Sync Vision:** To prevent noisy updates during physical token movement, the FoW updates only when a "Sync Vision" menu entry is activated.

### Display Modes
- **Normal Mode:**
  - **Unexplored:** Pitch black.
  - **Explored & Visible:** Fully lit map.
  - **Explored & NOT Visible:** Dimmed map (e.g., 30% opacity).
- **GM Override:** A "Fog of War: OFF" menu entry reveals the entire map for setup (grid alignment, panning/zooming), with a persistent visual reminder of the disabled state.

## 3. Interaction Mechanics

### Virtual Pointer
- **Implementation:** A pointer extended **1 inch** from the tracked index finger to prevent the hand from obscuring the table surface.

### Token Inspection (Exclusive Vision Mode)
- **Trigger:** Pointing at a token for **2 seconds**.
- **Behavior:** The system enters a temporary preview mode showing **only** what that specific token can see (LOS).
- **Transparency:** This mode **ignores Fog of War**, revealing unexplored areas within the token's direct LOS.
- **Exit:** Reverts to Normal Mode immediately when the pointing gesture ends.

### Door Interaction
- **Selection:** Pointing at a door for **2 seconds** "selects" it.
- **Action:** A top-level menu entry "Open/Close Door" becomes available to toggle its state, immediately affecting the global visibility geometry.

## 4. Implementation Details
- **Geometry Engine:** Use a 2D shadow-casting or recursive shadow-casting algorithm on the extracted SVG polygons.
- **Raster Integration:** The visibility mask will be composited with the SVG map and FoW bitmap in the renderer.
- **Testing:**
  - Unit tests for layer matching and multi-point origin calculations.
  - Deterministic LOS verification with mock wall layouts.
  - Integration tests for FoW persistence and IPC state management.
