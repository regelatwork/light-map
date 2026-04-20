# Tactical Cover & Reflex Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement automated AC/Reflex bonuses for Starfinder 1e based on Low Objects.

**Architecture:** Extend VisibilityEngine with Numba-optimized N^2 path tracing for visible tokens. Add a TacticalOverlayLayer for floating labels.

**Tech Stack:** Python (OpenCV, Numba, NumPy), TypeScript (Frontend).

---

### Task 1: Update Data Models

**Files:**
- Modify: `src/light_map/visibility/visibility_types.py`
- Modify: `frontend/src/types/system.ts`
- Modify: `src/light_map/core/common_types.py`
- Test: `tests/test_enum_sync.py`

**Step 1: Update VisibilityType**
Add `LOW_OBJECT = "low_object"` to both Python and TS enums.

**Step 2: Update Token Class**
Add `cover_bonus: int = 0` and `reflex_bonus: int = 0` to `Token` dataclass and its `to_dict` method.

**Step 3: Run sync test**
Run: `pytest tests/test_enum_sync.py`
Expected: PASS.

**Step 4: Commit**
```bash
git add src/light_map/visibility/visibility_types.py src/light_map/core/common_types.py frontend/src/types/system.ts
git commit -m "feat(models): add LOW_OBJECT type and cover/reflex bonus fields to Token"
```

---

### Task 2: SVG Extraction for Low Objects

**Files:**
- Modify: `src/light_map/rendering/svg/utils.py`
- Modify: `src/light_map/rendering/svg/blockers.py`
- Test: `tests/test_low_object_extraction.py` (New)

**Step 1: Write extraction test**
Verify layers with "low" + "object" are correctly identified and closed.

**Step 2: Update extraction logic**
Implement detection in `utils.py` and Ensure closed polygons in `blockers.py`.

**Step 3: Commit**
```bash
git add src/light_map/rendering/svg/ tests/test_low_object_extraction.py
git commit -m "feat(svg): extract low objects from SVG layers"
```

---

### Task 3: Render Low Objects to Mask

**Files:**
- Modify: `src/light_map/visibility/visibility_engine.py`
- Test: `tests/test_low_object_mask.py` (New)

**Step 1: Add MASK_VALUE_LOW = 50**
Add constant to `VisibilityEngine`.

**Step 2: Update update_blockers**
Use `cv2.fillPoly` to render low objects with value 50. Update priority sorting so LOW (50) is rendered before TALL (100) or WALL (255).

**Step 3: Commit**
```bash
git add src/light_map/visibility/visibility_engine.py tests/test_low_object_mask.py
git commit -m "feat(visibility): render low objects to blocker mask"
```

---

### Task 4: Numba-Optimized Cover Calculation

**Files:**
- Modify: `src/light_map/visibility/visibility_engine.py`
- Test: `tests/test_cover_logic.py` (New)

**Step 1: Implement `_numba_trace_path`**
Add Bresenham-lite path tracing helper.

**Step 2: Implement `_numba_calculate_cover_grade`**
Implement the ^2$ boundary-to-boundary logic with proximity rules.

**Step 3: Add Python wrapper**
Implement `calculate_token_cover_bonuses(source_token, target_token)`.

**Step 4: Commit**
```bash
git add src/light_map/visibility/visibility_engine.py tests/test_cover_logic.py
git commit -m "feat(visibility): implement high-resolution cover calculation"
```

---

### Task 5: Tactical Overlay Layer

**Files:**
- Create: `src/light_map/rendering/layers/tactical_overlay_layer.py`
- Modify: `src/light_map/core/layer_stack_manager.py`
- Test: `tests/test_tactical_overlay.py` (New)

**Step 1: Implement TacticalOverlayLayer**
Use `cv2.putText` to render AC/Reflex labels.

**Step 2: Update LayerStackManager**
Inject the layer above `MapLayer`, active in Exclusive Vision.

**Step 3: Update InteractiveApp**
Trigger cover calculation during Exclusive Vision scene processing.

**Step 4: Commit**
```bash
git add src/light_map/ tests/test_tactical_overlay.py
git commit -m "feat(rendering): add tactical overlay for cover bonuses"
```
