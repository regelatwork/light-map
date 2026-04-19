# Tall Object Blockers Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement "Tall Objects" in the visibility system that allow top-surface visibility but block vision behind, including high-ground logic.

**Architecture:** Use a "First Exit" rule in the Numba-optimized LOS check. Tall objects are rendered into the existing `blocker_mask` with a dedicated value (100). The LOS check allows exactly one transition from TALL to OPEN if the viewer started in a TALL zone.

**Tech Stack:** Python (OpenCV, NumPy, Numba), TypeScript (Frontend mirror).

---

### Task 1: Update Visibility Enums

**Files:**
- Modify: `src/light_map/visibility/visibility_types.py:11-14`
- Modify: `frontend/src/types/system.ts` (assuming path based on convention)
- Test: `tests/test_enum_sync.py`

**Step 1: Write the failing test**
Run `pytest tests/test_enum_sync.py` (it should pass currently). We will modify the enum first and then see it fail because the frontend is out of sync.

**Step 2: Update Python Enum**
Add `TALL_OBJECT = "tall_object"` to `VisibilityType`.

**Step 3: Run sync test to verify failure**
Run: `pytest tests/test_enum_sync.py`
Expected: FAIL due to mismatch with frontend.

**Step 4: Update Frontend Enum**
Add `TALL_OBJECT = "tall_object"` to the mirrored enum in `frontend/src/types/system.ts`.

**Step 5: Run sync test to verify success**
Run: `pytest tests/test_enum_sync.py`
Expected: PASS.

**Step 6: Commit**
```bash
git add src/light_map/visibility/visibility_types.py frontend/src/types/system.ts
git commit -m "feat(visibility): add TALL_OBJECT visibility type"
```

---

### Task 2: SVG Extraction for Tall Objects

**Files:**
- Modify: `src/light_map/rendering/svg/utils.py`
- Modify: `src/light_map/rendering/svg/blockers.py`
- Test: `tests/test_tall_object_extraction.py` (New)

**Step 1: Create extraction test**
Create `tests/test_tall_object_extraction.py` that creates a mock SVG with a layer named "Tall Objects" and verifies a `TALL_OBJECT` blocker is extracted and closed.

**Step 2: Update `get_visibility_type`**
Implement the "tall" + "object" detection in `src/light_map/rendering/svg/utils.py`.

**Step 3: Ensure shapes are closed**
Update `extract_visibility_blocker` in `src/light_map/rendering/svg/blockers.py` to connect the last point to the first for `TALL_OBJECT` types.

**Step 4: Run tests**
Run: `pytest tests/test_tall_object_extraction.py`
Expected: PASS.

**Step 5: Commit**
```bash
git add src/light_map/rendering/svg/ tests/test_tall_object_extraction.py
git commit -m "feat(svg): extract tall objects from specific layers"
```

---

### Task 3: Render Tall Objects to Mask

**Files:**
- Modify: `src/light_map/visibility/visibility_engine.py`
- Test: `tests/test_visibility_engine_mask.py` (New)

**Step 1: Add Constant**
Add `MASK_VALUE_TALL = 100` to `VisibilityEngine`.

**Step 2: Update `update_blockers`**
Use `cv2.fillPoly` to render `TALL_OBJECT` blockers into `self.blocker_mask` using `MASK_VALUE_TALL`.

**Step 3: Write mask verification test**
Verify pixels inside a tall object polygon in the mask have value 100.

**Step 4: Commit**
```bash
git add src/light_map/visibility/visibility_engine.py tests/test_visibility_engine_mask.py
git commit -m "feat(visibility): render tall objects to blocker mask"
```

---

### Task 4: Implement "First Exit" LOS Logic

**Files:**
- Modify: `src/light_map/visibility/visibility_engine.py`
- Test: `tests/test_tall_object_visibility.py` (New)

**Step 1: Update Numba LOS signatures**
Update `_numba_is_line_obstructed` to accept `viewer_starts_in_tall` (bool).

**Step 2: Implement "First Exit" logic in Numba**
Add the state tracking for `has_exited_initial_tall_zone`.

**Step 3: Update BFS and propagation**
Update `_numba_bfs_flood_fill` and its callers to calculate and pass `viewer_starts_in_tall`.

**Step 4: Write comprehensive logic tests**
Implement the scenarios: Ground->Plateau (See top), Ground->Behind (Blocked), Plateau->Ground (See bottom).

**Step 5: Run tests**
Run: `pytest tests/test_tall_object_visibility.py`
Expected: PASS.

**Step 6: Commit**
```bash
git add src/light_map/visibility/visibility_engine.py tests/test_tall_object_visibility.py
git commit -m "feat(visibility): implement First Exit LOS rule for tall objects"
```

---

### Task 5: Fog of War Integration

**Files:**
- Modify: `src/light_map/visibility/fow_manager.py`
- Test: `tests/test_tall_object_discovery.py` (New)

**Step 1: Update Discovery Logic**
Ensure that when a tall object is visible, it is marked as "discovered" in the FoW system.

**Step 2: Verify FoW mask includes tall objects**
Write a test to ensure visible tall object surfaces are not shrouded.

**Step 3: Commit**
```bash
git add src/light_map/visibility/fow_manager.py tests/test_tall_object_discovery.py
git commit -m "feat(fow): allow discovery of tall object surfaces"
```
