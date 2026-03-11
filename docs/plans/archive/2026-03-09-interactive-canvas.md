# Interactive Canvas with Draggable Grid Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a responsive SVG-based schematic view that visualizes world state (tokens, grid, map) and allows interactive panning, zooming, and grid adjustment.

**Architecture:** Use layered SVG elements where each layer (Grid, Tokens, Interaction) is a separate component. Interaction state (pan/zoom) is managed locally in the canvas component, while world state is consumed via `useSystemState`.

**Tech Stack:** React (TypeScript), SVG, Tailwind CSS, FastAPI (Python).

______________________________________________________________________

### Task 0: Backend - Add Grid Config Endpoint

**Files:**

- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Add GridConfig model**

```python
class GridConfig(BaseModel):
    offset_x: float
    offset_y: float
```

**Step 2: Add POST /config/grid endpoint**

```python
@app.post("/config/grid")
def set_grid_config(config: GridConfig):
    res = DetectionResult(
        timestamp=time.monotonic_ns(),
        type=ResultType.ACTION,
        data={"action": "UPDATE_GRID", "offset_x": config.offset_x, "offset_y": config.offset_y},
    )
    results_queue.put(res)
    return {"status": "injected"}
```

**Step 3: Commit**
Run: `git add src/light_map/vision/remote_driver.py && git commit -m "feat(remote-driver): add grid config update endpoint"`

______________________________________________________________________

### Task 1: Basic Canvas Structure and Pan/Zoom

**Files:**

- Create: `frontend/src/components/SchematicCanvas.tsx`
- Modify: `frontend/src/components/Dashboard.tsx`

**Step 1: Create the SchematicCanvas component**
Implement a base SVG container that handles mouse events for panning and zooming.

**Step 2: Add zooming and panning logic**
Use `viewBox` manipulation to achieve smooth zooming and panning.

**Step 3: Integrate into Dashboard**
Replace the placeholder in `Dashboard.tsx` with the new `SchematicCanvas`.

**Step 4: Commit**
Run: `git add frontend/src/components && git commit -m "feat(frontend): implement basic schematic canvas with pan and zoom"`

______________________________________________________________________

### Task 2: Implement Grid Layer

**Files:**

- Create: `frontend/src/components/GridLayer.tsx`
- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Create the GridLayer component**
Render a set of `<line>` elements based on the current system configuration (PPI, offset, resolution).

**Step 2: Add GridLayer to the canvas**
Ensure it stays aligned during pan and zoom.

**Step 3: Commit**
Run: `git add frontend/src/components && git commit -m "feat(frontend): add grid rendering layer to canvas"`

______________________________________________________________________

### Task 4: Implement Token Layer

**Files:**

- Create: `frontend/src/components/TokenLayer.tsx`
- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Create the TokenLayer component**
Render `<circle>` or `<rect>` elements for each token in the `SystemState`. Show the token ID as text.

**Step 2: Add TokenLayer to the canvas**
Verify that tokens move in real-time as the WebSocket state updates.

**Step 3: Commit**
Run: `git add frontend/src/components && git commit -m "feat(frontend): add token visualization layer to canvas"`

______________________________________________________________________

### Task 5: Draggable Grid Interaction

**Files:**

- Modify: `frontend/src/components/GridLayer.tsx`
- Create: `frontend/src/services/api.ts`

**Step 1: Add drag handle to the GridLayer**
Implement a visual handle (e.g., a circle) that can be dragged to adjust the `grid_offset_x` and `grid_offset_y`.

**Step 2: Implement API client**
Create `frontend/src/services/api.ts` with a `saveGridConfig` function to persist grid changes to the backend.

**Step 3: Persist grid adjustments**
When the handle is dropped, send the new offsets to the FastAPI backend.

**Step 4: Commit**
Run: `git add frontend/src && git commit -m "feat(frontend): implement draggable grid and persistence API"`

______________________________________________________________________

### Task 6: Verification and Final Polishing

**Files:**

- Create: `frontend/src/components/SchematicCanvas.test.tsx`

**Step 1: Write integration tests**
Verify that the canvas renders and responds to state updates correctly.

**Step 2: Final build and lint check**
Run: `cd frontend && npm run format && npm run build && npm run test`
Expected: SUCCESS.

**Step 3: Commit**
Run: `git add frontend && git commit -m "test(frontend): add canvas integration tests and polish UI"`
