# Interactive Canvas Layers: Map, Fog of War, and Doors

**Goal:** Complete the interactive schematic view in the frontend by adding the missing Map (SVG), Fog of War (FoW), and Door layers.

**Background:** The frontend currently only shows the Grid and Tokens. This plan bridges the gap by exposing necessary assets from the Python backend and implementing the corresponding React layers.

______________________________________________________________________

### Task 1: Backend Asset Exposure

**Files:**

- Modify: `src/light_map/__main__.py`
- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Expose `current_map_path` in World State mirror**
In `render_cb` of `__main__.py`, add `current_map_path` to the `state_mirror["config"]` object. This allows the frontend to know which map is loaded.

**Step 2: Add Map and FOW endpoints to the FastAPI Remote Driver**
In `remote_driver.py`, implement two new GET endpoints:

- `/map/svg`: Returns the SVG file of the current map (using `FileResponse`).
- `/map/fow`: Returns the `fow.png` mask of the current map. It must derive the FOW path from the map filename and hash, similar to `MapConfigManager.get_fow_dir()`.

**Step 3: Verification**
Load a map in the backend and verify that `curl http://localhost:8000/map/svg` and `curl http://localhost:8000/map/fow` return valid data.

______________________________________________________________________

### Task 2: Frontend Type and State Extension

**Files:**

- Modify: `frontend/src/types/system.ts`

**Step 1: Update `SystemConfig` and `SystemState`**
Add `current_map_path` and `blockers` (as an array of `VisibilityBlocker`) to the state interfaces.

______________________________________________________________________

### Task 3: Implement Map Layer

**Files:**

- Create: `frontend/src/components/MapLayer.tsx`
- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Create the `MapLayer` component**

- Use an SVG `<image>` element.
- The `href` should point to `/map/svg` with a cache-busting timestamp or based on `current_map_path`.
- Ensure it covers the intended map area (at world 0,0).

______________________________________________________________________

### Task 4: Implement Door Layer

**Files:**

- Create: `frontend/src/components/DoorLayer.tsx`
- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Create the `DoorLayer` component**

- Iterate over `world.blockers`.
- Draw SVG lines/shapes for doors.
- Closed doors: thick yellow line with black outline.
- Open doors: yellow circles at endpoints.
- Match styles from the Python `DoorLayer.py`.

______________________________________________________________________

### Task 5: Implement Fog of War Layer

**Files:**

- Create: `frontend/src/components/FowLayer.tsx`
- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Create the `FowLayer` component**

- Use an SVG `<image>` element pointing to `/map/fow`.
- Apply an SVG mask or CSS filter (`opacity`) to the canvas or a overlay group to represent the "fog".

______________________________________________________________________

### Task 6: Final Integration and Verification

**Files:**

- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Order Layers correctly**
The rendering stack (bottom to top) should be:

1. Map Layer
1. Door Layer
1. Grid Layer
1. Token Layer
1. Fog of War Layer (as a mask or semi-transparent overlay)

**Step 2: Verification**

- Run `vitest` to ensure no regressions.
- Verify visually that the map, doors, and fog appear and are correctly aligned with the grid and tokens.
