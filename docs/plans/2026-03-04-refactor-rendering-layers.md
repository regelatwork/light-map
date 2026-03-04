# Refactor Rendering Layers Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor overloaded rendering layers (FogOfWar, HandMask, Scene, Visibility, Cursor) to adhere to the Single Responsibility Principle (SRP) by extracting state management, persistence, and complex coordinate logic into dedicated managers and helper classes.

**Architecture:**

- **Layers** should be "dumb" and focus strictly on producing `ImagePatch` objects from provided state.
- **Managers** (e.g., `FogOfWarManager`) handle persistent state, file I/O, and business logic.
- **WorldState** serves as the bridge, holding the latest computed results for the layers to consume.

**Tech Stack:** Python, NumPy, OpenCV, Pytest (TDD)

______________________________________________________________________

### Task 1: Refactor FogOfWarLayer

**Goal:** Extract state management and persistence to `FogOfWarManager`.

**Files:**

- Create: `src/light_map/fow_manager.py`
- Modify: `src/light_map/fow_layer.py`
- Modify: `src/light_map/interactive_app.py`
- Test: `tests/test_fow_manager.py`

**Step 1: Create `FogOfWarManager` tests**
Write tests for loading, saving, and unioning masks in a dedicated manager class.

**Step 2: Implement `FogOfWarManager`**
Move logic from `FogOfWarLayer.__init__`, `load`, `save`, `reveal_area`, and `reset` into `FogOfWarManager`.

**Step 3: Update `FogOfWarLayer`**
Refactor the layer to accept a `FogOfWarManager` (or just consume the masks from it) and focus only on `_generate_patches`.

**Step 4: Update `InteractiveApp`**
Instantiate the manager and pass it to the layer.

**Step 5: Verify and Commit**
Run `pytest tests/test_fow_layer.py tests/test_fow_manager.py` and commit.

______________________________________________________________________

### Task 2: Refactor HandMaskLayer

**Goal:** Move coordinate transformations and hull dilation to `HandMasker`.

**Files:**

- Modify: `src/light_map/vision/hand_masker.py`
- Modify: `src/light_map/hand_mask_layer.py`
- Test: `tests/test_hand_masker.py`

**Step 1: Update `HandMasker` interface**
Add a method to `HandMasker` that takes raw hands and returns a list of "ready-to-render" hulls (projector space, dilated).

**Step 2: Move logic from `HandMaskLayer` to `HandMasker`**
Move the `transform_pts` and dilation logic into `HandMasker.get_mask_hulls`.

**Step 3: Simplify `HandMaskLayer`**
The layer should now just call `masker.get_mask_hulls()` and draw the resulting polygons onto patches.

**Step 4: Verify and Commit**
Run `pytest tests/test_hand_masker.py tests/test_hand_mask_layer.py` and commit.

______________________________________________________________________

### Task 3: Refactor SceneLayer

**Goal:** Separate Modern Scene logic from Legacy Bridge logic.

**Files:**

- Create: `src/light_map/legacy_scene_layer.py`
- Modify: `src/light_map/scene_layer.py`
- Modify: `src/light_map/interactive_app.py`

**Step 1: Create `LegacySceneLayer`**
Move the "black is transparent" heuristic and legacy `scene.render(buffer)` bridge to this new class.

**Step 2: Clean up `SceneLayer`**
Refactor `SceneLayer` to handle modern `Scene` objects that might return their own patches or use a more standard rendering interface (TBD/Minimal for now).

**Step 3: Update `InteractiveApp`**
Use `LegacySceneLayer` where appropriate (if any legacy scenes remain) or ensure the bridge is explicitly handled.

**Step 4: Verify and Commit**
Run `pytest tests/test_scene_layer.py` and commit.

______________________________________________________________________

### Task 4: Refactor VisibilityLayer

**Goal:** Standardize state consumption from `WorldState`.

**Files:**

- Modify: `src/light_map/visibility_layer.py`
- Modify: `src/light_map/interactive_app.py`

**Step 1: Modify `VisibilityLayer` to use `WorldState`**
Instead of `set_mask()`, the layer should look for a `visibility_mask` in `WorldState`.

**Step 2: Update `InteractiveApp` to store mask in `WorldState`**
Move the mask storage from the layer instance to `WorldState`.

**Step 3: Verify and Commit**
Run `pytest tests/test_visibility_layer.py` and commit.

______________________________________________________________________

### Task 5: Refactor CursorLayer

**Goal:** Extract cursor state logic.

**Files:**

- Modify: `src/light_map/cursor_layer.py`

**Step 1: Move cursor calculation to a helper or `WorldState`**
Calculate the 1-inch pointer extension outside the render loop if possible, or at least extract the geometric calculation to a pure function.

**Step 2: Simplify `CursorLayer`**
The layer should only handle drawing the reticle at the provided coordinates.

**Step 3: Verify and Commit**
Run `pytest tests/test_cursor_layer.py` and commit.
