# Frontend Synchronization and Fog of War Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve frontend synchronization issues (map loading, menu state) and enable the Fog of War layer in the schematic view.

**Architecture:**

1. **Frontend Integration**: Add the missing `FowLayer` component to `SchematicCanvas.tsx`.
1. **Initial State Sync**: Modify the WebSocket `ConnectionManager` to broadcast the current state immediately upon a new connection.
1. **Robust Metadata**: Ensure `fow_timestamp` and other version metadata are consistently sent to trigger frontend refreshes.

**Tech Stack:** Python (FastAPI, WebSockets), React (TypeScript).

______________________________________________________________________

### Task 1: Add Fog of War Layer to Frontend

**Files:**

- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Import FowLayer**
Add `import { FowLayer } from './FowLayer';` to the imports.

**Step 2: Add FowLayer to the SVG stack**
Place `<FowLayer />` inside the SVG, before the interactive layers (DoorLayer, TokenLayer) so it's behind them but over the map.

```tsx
          <g transform={`rotate(${rotation} ${centerX} ${centerY})`}>
            <MapLayer />
            <FowLayer />
            <DoorLayer />
            <TokenLayer />
          </g>
```

**Step 3: Commit**

```bash
git add frontend/src/components/SchematicCanvas.tsx
git commit -m "feat(frontend): add FowLayer to SchematicCanvas"
```

### Task 2: Immediate State Sync on Connection

**Files:**

- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Update ConnectionManager to support immediate sync**
Modify `ConnectionManager.connect` to optionally accept the current state and send it immediately.

**Step 2: Pass current state in websocket_endpoint**
In `websocket_endpoint`, fetch the current state from `state_mirror` and send it immediately after calling `manager.connect(websocket)`.

**Step 3: Commit**

```bash
git add src/light_map/vision/remote_driver.py
git commit -m "fix(remote-driver): send initial state immediately on websocket connection"
```

### Task 3: Ensure Menu State Initialization

**Files:**

- Modify: `src/light_map/__main__.py`

**Step 1: Force initial world and menu sync**
Ensure `last_world_ts` and `last_menu_ts` are initialized to a value that forces an update on the first frame of `render_cb`. (They are already -1, so this might be fine, but verify).

**Step 2: Commit (if changes needed)**

```bash
git add src/light_map/__main__.py
git commit -m "fix(backend): ensure initial menu and world state are synced to mirror"
```

### Task 4: Fix Map Dimension Sync

**Files:**

- Modify: `src/light_map/__main__.py`

**Step 1: Update config mirror when map is loaded**
In `render_cb`, ensure `map_width` and `map_height` are updated in `state_mirror["config"]` whenever `app.current_map_path` changes.

**Step 2: Commit**

```bash
git add src/light_map/__main__.py
git commit -m "fix(backend): sync map dimensions to state mirror when map changes"
```

### Task 5: Verification

**Step 1: Run Backend Tests**
Run `pytest tests/test_remote_driver_ws.py` to verify WebSocket behavior.

**Step 2: Manual Verification**

1. Start backend.
1. Load frontend.
1. Verify Map and Fog of War are visible.
1. Verify Menu appears when summoned.
