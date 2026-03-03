# SVG Wall Support and Fog of War Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement interactive visibility and exploration tracking using SVG-encoded walls/doors and persistent Fog of War bitmaps.

**Architecture:** Extend `SVGLoader` to extract visibility blockers, implement a 2D shadowcasting engine for LOS calculations, and manage a persistent PNG-based exploration mask. Integration via the `Renderer` for compositing and `InputProcessor` for dwell-based interactions.

**Tech Stack:** Python, OpenCV (for mask operations), `svgelements` (SVG parsing), `numpy`.

---

### Task 1: SVG Blocker Extraction

**Goal:** Extend `SVGLoader` to categorize paths by layer name.

**Files:**
- Modify: `src/light_map/svg_loader.py`
- Test: `tests/test_svg_loader_visibility.py`

**Step 1: Write the failing test**
Create `tests/test_svg_loader_visibility.py` to test layer detection for "Walls", "Doors", and "Unbreakable Windows".

```python
import pytest
from src.light_map.svg_loader import SVGLoader
import os

def test_extract_visibility_layers(tmp_path):
    svg_content = """<svg width="100" height="100">
      <g id="Walls_Layer"><path d="M 0 0 L 10 10" /></g>
      <g id="Secret_Doors"><path d="M 20 20 L 30 30" /></g>
      <g id="Unbreakable_Windows"><path d="M 40 40 L 50 50" /></g>
    </svg>"""
    svg_path = tmp_path / "test.svg"
    svg_path.write_text(svg_content)
    
    loader = SVGLoader(str(svg_path))
    blockers = loader.get_visibility_blockers()
    
    assert len(blockers['walls']) == 1
    assert len(blockers['doors']) == 1
    assert len(blockers['windows']) == 1
```

**Step 2: Run test to verify it fails**
`pytest tests/test_svg_loader_visibility.py -v`

**Step 3: Implement `get_visibility_blockers`**
Add logic to `SVGLoader` to traverse elements and check group/parent IDs for keywords.

**Step 4: Run test to verify it passes**
`pytest tests/test_svg_loader_visibility.py -v`

**Step 5: Commit**
`git add src/light_map/svg_loader.py tests/test_svg_loader_visibility.py && git commit -m "feat: Add visibility blocker extraction to SVGLoader"`

---

### Task 2: 2D Shadowcasting Engine (Single Point)

**Goal:** Implement a basic visibility polygon generator using a shadowcasting algorithm.

**Files:**
- Create: `src/light_map/visibility.py`
- Test: `tests/test_visibility_logic.py`

**Step 1: Write failing test for simple LOS**
Test that a point at (50, 50) surrounded by a square wall (0,0 to 100,100) sees the whole square.

**Step 2: Run test to verify it fails**
`pytest tests/test_visibility_logic.py -v`

**Step 3: Implement Shadowcasting**
Add `calculate_visibility(origin, segments, max_range)` in `src/light_map/visibility.py`.

**Step 4: Run test to verify it passes**
`pytest tests/test_visibility_logic.py -v`

**Step 5: Commit**
`git add src/light_map/visibility.py tests/test_visibility_logic.py && git commit -m "feat: Add core 2D visibility engine"`

---

### Task 3: Starfinder 1e Multi-Point Vision

**Goal:** Union multiple visibility polygons for tokens of size S.

**Files:**
- Modify: `src/light_map/visibility.py`
- Test: `tests/test_visibility_starfinder.py`

**Step 1: Write test for 2x2 token vision**
Verify vision is calculated from 9 corners + center.

**Step 2: Run test to verify it fails**

**Step 3: Implement `get_token_vision(token_rect, segments, range)`**
Logic to calculate and union polygons.

**Step 4: Run test to verify it passes**

**Step 5: Commit**
`git add src/light_map/visibility.py tests/test_visibility_starfinder.py && git commit -m "feat: Implement Starfinder 1e multi-point vision rules"`

---

### Task 4: Fog of War Persistence

**Goal:** Manage the 16x grid PNG bitmap.

**Files:**
- Create: `src/light_map/fow_manager.py`
- Test: `tests/test_fow_persistence.py`

**Step 1: Write test for FoW update and save**
Initialize a 100x100 grid (1600x1600 mask), reveal a circle, save, and reload.

**Step 2: Run test to verify it fails**

**Step 3: Implement `FogOfWarManager`**
Methods: `update_revealed(polygons)`, `save(path)`, `load(path)`, `reset()`.

**Step 4: Run test to verify it passes**

**Step 5: Commit**
`git add src/light_map/fow_manager.py tests/test_fow_persistence.py && git commit -m "feat: Add Fog of War persistence manager"`

---

### Task 5: Renderer Integration

**Goal:** Composite Map + FoW + Current Visibility.

**Files:**
- Modify: `src/light_map/renderer.py`
- Modify: `src/light_map/map_layer.py`

**Step 1: Update Renderer to accept multiple masks**
Add logic to apply the visibility mask (binary) and FoW mask (alpha) during composition.

**Step 2: Integrate into MapLayer**
`MapLayer` should hold the `FogOfWarManager` and request LOS updates.

**Step 3: Test rendering output**
Use a regression test in `tests/test_renderer_visibility.py` to check pixel values.

**Step 4: Commit**
`git add src/light_map/renderer.py src/light_map/map_layer.py && git commit -m "feat: Integrate visibility masks into renderer"`

---

### Task 6: Interaction & Dwell Logic

**Goal:** Implement the 1-inch virtual pointer and 2-second dwell for selection.

**Files:**
- Modify: `src/light_map/input_processor.py`
- Modify: `src/light_map/scenes/map_scene.py`

**Step 1: Implement virtual pointer offset**
Add 1-inch (PPI-scaled) offset to the tracked index finger position.

**Step 2: Implement Dwell Timer**
Logic in `MapScene` or `InputProcessor` to track how long a pointer stays on an object.

**Step 3: Test dwell triggering**
Mock hand input hovering for 2.1s and verify the event triggers.

**Step 4: Commit**
`git add src/light_map/input_processor.py src/light_map/scenes/map_scene.py && git commit -m "feat: Add virtual pointer and dwell-based selection logic"`

---

### Task 7: Menu Integration

**Goal:** Add FOV controls and Door toggles to the menu.

**Files:**
- Modify: `src/light_map/menu_config.py`
- Modify: `src/light_map/interactive_app.py`

**Step 1: Add "Sync Vision" and "Open/Close Door" menu entries**
Update configuration to show these context-sensitive items.

**Step 2: Implement menu actions**
Wire the menu actions to `FogOfWarManager` and the door state list.

**Step 3: Commit**
`git add src/light_map/menu_config.py src/light_map/interactive_app.py && git commit -m "feat: Add Fog of War and Door controls to menu"`
