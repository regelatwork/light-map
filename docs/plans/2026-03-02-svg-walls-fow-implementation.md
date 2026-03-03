# SVG Wall Support and Fog of War Implementation Plan (Refined)

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement interactive visibility and exploration tracking using SVG-encoded walls/doors and persistent Fog of War bitmaps.

**Architecture:** Extend `SVGLoader` to extract visibility blockers, implement a 2D shadowcasting engine for LOS calculations, and manage a persistent PNG-based exploration mask. Integration via the `Renderer` for compositing and `InputProcessor` for dwell-based interactions.

**Tech Stack:** Python, OpenCV (for mask operations), `svgelements` (SVG parsing), `numpy`.

---

### Task 1: SVG Blocker Extraction & Data Types

**Goal:** Extend `SVGLoader` to categorize paths by layer name and define a robust `VisibilityBlocker` data structure.

**Files:**
- Create: `src/light_map/visibility_types.py`
- Modify: `src/light_map/svg_loader.py`
- Test: `tests/test_svg_loader_visibility.py`

**Step 1: Define `VisibilityBlocker` and `VisibilityState`**
Use `dataclass` to store geometry, layer name, type (WALL, DOOR, WINDOW), and state (OPEN, CLOSED).

**Step 2: Implement `get_visibility_blockers` in `SVGLoader`**
Logic to traverse elements and check group/parent IDs for keywords (case-insensitive substring).

**Step 3: Write and run tests**
Verify layer detection for "Walls", "Doors", and "Unbreakable Windows" using mock SVGs.

**Step 4: Commit**
`git commit -m "feat: Add VisibilityBlocker types and SVG extraction logic"`

---

### Task 2: 2D Shadowcasting Engine with Caching

**Goal:** Implement a high-performance visibility polygon generator with a geometry cache.

**Files:**
- Create: `src/light_map/visibility_engine.py`
- Test: `tests/test_visibility_logic.py`

**Step 1: Implement `GeometryCache`**
Stores static wall segments and only updates when doors/windows change state.

**Step 2: Implement `calculate_visibility`**
Recursive shadowcasting or ray-casting algorithm. Returns a list of points (polygon).

**Step 3: Implement `VisibilityCache`**
Caches the final LOS polygon for a token ID and position. Invalidates if the token moves > 0.1 inches or `GeometryCache` is dirty.

**Step 4: Write and run tests**
Test LOS through doors (open vs closed) and performance with many segments.

**Step 5: Commit**
`git commit -m "feat: Add visibility engine with geometry and mask caching"`

---

### Task 3: Starfinder 1e Multi-Point Vision Union

**Goal:** Union multiple visibility polygons for tokens of size S using OpenCV `bitwise_or`.

**Files:**
- Modify: `src/light_map/visibility_engine.py`
- Test: `tests/test_visibility_starfinder.py`

**Step 1: Implement `get_token_vision_mask(token_rect, segments, range)`**
- Calculate vision from center + corners.
- Render each polygon into a single-channel mask.
- Use `cv2.bitwise_or` to union them.

**Step 2: Write and run tests**
Verify 1x1, 2x2, and 3x3 token vision patterns.

**Step 3: Commit**
`git commit -m "feat: Implement Starfinder 1e multi-point vision mask union"`

---

### Task 4: Fog of War Layer & Persistence

**Goal:** Manage the 16x grid PNG bitmap and its persistence.

**Files:**
- Create: `src/light_map/fow_layer.py`
- Test: `tests/test_fow_layer.py`

**Step 1: Implement `FogOfWarLayer`**
- Extends `Layer` for rendering.
- Manages an in-memory `cv2` mask (16x grid resolution).
- Handles `load(map_path)` and `save(map_path)`.

**Step 2: Implement "Explored but Not Visible" dimming**
The layer will render a dimmed version of the map for pixels that are `explored == True` and `visible == False`.

**Step 3: Commit**
`git commit -m "feat: Add FogOfWarLayer and persistence logic"`

---

### Task 5: Renderer Multi-Layer Composition

**Goal:** Composite Map, FoW, and Current Visibility layers.

**Files:**
- Modify: `src/light_map/renderer.py`
- Modify: `src/light_map/interactive_app.py`

**Step 1: Update Layer stack in `InteractiveApp`**
1. `MapLayer` (Bottom)
2. `FogOfWarLayer` (Masks Map)
3. `VisibilityLayer` (Real-time LOS)
4. `MenuLayer` (Top)

**Step 2: Implement "Exclusive Vision Mode"**
A flag to swap the normal layer stack for one that only renders the single token's vision.

**Step 3: Commit**
`git commit -m "feat: Implement multi-layer composition for visibility and FoW"`

---

### Task 6: Interaction Dwell & Virtual Pointer

**Goal:** Implement 1-inch offset and 2-second dwell logic for selection.

**Files:**
- Create: `src/light_map/dwell_tracker.py`
- Modify: `src/light_map/input_processor.py`

**Step 1: Implement `DwellTracker`**
Tracks `(x, y)` position over time. Triggers an `ON_DWELL` event after 2 seconds of stability.

**Step 2: Implement 1-inch Virtual Pointer**
Apply PPI-based offset in `InputProcessor` to the index finger tip.

**Step 3: Write and run tests**
Verify dwell triggering and pointer offset accuracy.

**Step 4: Commit**
`git commit -m "feat: Add DwellTracker and virtual pointer logic"`

---

### Task 7: Session Persistence & Menu Integration

**Goal:** Persist door states and add FOV controls to the menu.

**Files:**
- Modify: `src/light_map/session_manager.py`
- Modify: `src/light_map/menu_config.py`

**Step 1: Persist Door States**
Update `SessionManager` to save the state (Open/Closed) of all interactive blockers in the map session.

**Step 2: Add Menu Entries**
"Sync Vision", "Reset FoW", "Toggle Door", and "GM: Disable FoW".

**Step 3: Final Integration Test**
Run a full scenario: Load map -> Move tokens -> Sync Vision -> Save/Reload.

**Step 4: Commit**
`git commit -m "feat: Add session persistence for door states and final menu integration"`
