# SVG Wall Support and Fog of War Implementation Plan (Final)

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement interactive visibility and exploration tracking using SVG-encoded walls/doors and persistent Fog of War bitmaps.

**Architecture:** Extend `SVGLoader` to extract visibility blockers, implement a 2D shadowcasting engine for LOS calculations, and manage a persistent PNG-based exploration mask. Integration via the `Renderer` for compositing and `InputProcessor` for dwell-based interactions.

**Coordinate Mapping:**

- **Scale:** `16 / MapEntry.grid_spacing_svg` (maps SVG units to the 16x-resolution FoW pixels).
- **Origin:** `(MapEntry.grid_origin_svg_x, MapEntry.grid_origin_svg_y)`.

**Tech Stack:** Python, OpenCV (for mask operations), `svgelements` (SVG parsing), `numpy`.

______________________________________________________________________

### Task 1: SVG Blocker Extraction & Data Types

**Goal:** Extend `SVGLoader` to categorize paths by layer name and define `VisibilityBlocker`.

**Files:**

- Create: `src/light_map/visibility_types.py`
- Modify: `src/light_map/svg_loader.py`
- Test: `tests/test_svg_loader_visibility.py`

**Step 1: Define `VisibilityBlocker` and `VisibilityType`**
Include `segments: List[Tuple[float, float]]`, `type: VisibilityType` (WALL, DOOR, WINDOW), and `is_open: bool`.

**Step 2: Implement `get_visibility_blockers` in `SVGLoader`**
Substring matching for "Wall", "Door", "Window", and "Unbreakable". Handle nested transforms.

**Step 3: Commit**
`git commit -m "feat: Add VisibilityBlocker types and SVG extraction logic"`

______________________________________________________________________

### Task 2: 2D Shadowcasting Engine with Spatial Hashing

**Goal:** Implement high-performance visibility calculation with segment pruning.

**Files:**

- Create: `src/light_map/visibility_engine.py`
- Test: `tests/test_visibility_logic.py`

**Step 1: Implement Spatial Hashing**
Divide the map into 10x10 grid tiles to quickly prune far-away wall segments for each ray-cast.

**Step 2: Implement `VisibilityCache`**
Key: `(token_id, int(grid_x), int(grid_y))`. This provides 1-cell hysteresis for physical token micro-movements.

**Step 3: Write and run tests**
Test LOS through doors and performance with 500+ segments.

**Step 4: Commit**
`git commit -m "feat: Add visibility engine with spatial hashing and jitter-resistant caching"`

______________________________________________________________________

### Task 3: Starfinder 1e Multi-Point Vision Union

**Goal:** Union multiple visibility polygons for tokens of size S using OpenCV `bitwise_or`.

**Files:**

- Modify: `src/light_map/visibility_engine.py`
- Test: `tests/test_visibility_starfinder.py`

**Step 1: Implement `get_token_vision_mask`**
Calculate vision from center + corners. Union polygons using `cv2.fillPoly` and `cv2.bitwise_or`.

**Step 2: Handle Out-of-Bounds**
If token is outside map limits, return an all-black mask (0.0 visibility).

**Step 3: Commit**
`git commit -m "feat: Implement Starfinder 1e multi-point vision mask union with OOB safety"`

______________________________________________________________________

### Task 4: Fog of War Layer & Resilience

**Goal:** Manage the persistent 16x grid PNG bitmap with error handling.

**Files:**

- Create: `src/light_map/fow_layer.py`
- Test: `tests/test_fow_layer.py`

**Step 1: Implement FoW PNG Loading with Try-Except**
If the PNG is missing or corrupted, initialize a blank (0,0,0) mask.

**Step 2: Implement "Explored but Not Visible" dimming**
`mask = (explored_bitmap == 255) & (visible_mask == 0)`. Render at 30% alpha.

**Step 3: Commit**
`git commit -m "feat: Add resilient FoWLayer with explored-dimming support"`

______________________________________________________________________

### Task 5: Renderer Multi-Layer Composition

**Goal:** Composite Map, FoW, and Visibility layers.

**Step 1: Update Layer Stack**
Stack: `MapLayer` -> `FoWLayer` -> `VisibilityLayer`.

**Step 2: Implement Exclusive Vision Mode**
Toggle logic in `InteractiveApp` to render only the pointed-at token's mask.

**Step 3: Commit**
`git commit -m "feat: Implement multi-layer composition for visibility and FoW"`

______________________________________________________________________

### Task 6: Interaction Dwell & Virtual Pointer

**Goal:** Implement 1-inch offset and 2-second dwell logic.

**Step 1: Implement `DwellTracker`**
Track index finger stability (within 0.5-inch radius) for 2.0s.

**Step 2: Implement 1-inch Virtual Pointer**
Apply `config.projector_ppi` based offset to pointer coordinates.

**Step 3: Commit**
`git commit -m "feat: Add DwellTracker and virtual pointer logic"`

______________________________________________________________________

### Task 7: Session Persistence & Menu Integration

**Goal:** Persist door states and add FOV controls.

**Step 1: Persist Door States in `SessionManager`**
Save `door_states: Dict[str, bool]` in the session JSON.

**Step 2: Add Menu Entries**
"Sync Vision", "Reset FoW", "Toggle Door", "GM: Disable FoW".

**Step 3: Commit**
`git commit -m "feat: Add door state persistence and final menu integration"`
