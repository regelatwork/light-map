# SVG Radial Gradients and Masks Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add support for radial gradients and masking in the SVG renderer to fix rendering issues in `maps/fortunes-hart-space.svg`.

**Architecture:** 
- Enhance SVG parsing to capture nested `mask` and `gradient` structures.
- Implement a radial gradient generator using NumPy/OpenCV.
- Implement a masking pass in the SVG traversal that renders mask contents and applies them to the target element's alpha channel.

**Tech Stack:** Python, svgelements, OpenCV, NumPy.

---

### Task 1: Update SVG library to capture nested structures

**Files:**
- Modify: `/home/rchandia/light_map/.venv/lib/python3.12/site-packages/svgelements/svgelements.py` (ALREADY DONE)

**Note:** This task is already completed by the previous `replace` call. It ensures `mask`, `radialGradient`, and `linearGradient` are parsed as `Group` objects.

### Task 2: Update Renderer Signatures to include SVG root

**Files:**
- Modify: `src/light_map/rendering/svg/renderer.py`
- Modify: `src/light_map/rendering/svg/loader.py`

**Step 1: Update `render_image_element`, `render_text_element`, and `render_shape_element` to accept `svg` root.**

```python
def render_image_element(
    element: svgelements.Image,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
    render_w: int,
    render_h: int,
    svg: svgelements.SVG, # Added
):
```

**Step 2: Update `SVGLoader._render_internal` to pass `self.svg` to these functions.**

**Step 3: Commit.**

```bash
git add src/light_map/rendering/svg/
git commit -m "refactor: pass SVG root to rendering functions for resource lookup"
```

### Task 3: Implement Radial Gradient Rendering

**Files:**
- Modify: `src/light_map/rendering/svg/renderer.py`

**Step 1: Implement `get_gradient_stops(gradient_elem, svg)` to resolve stops (including `xlink:href` references).**

**Step 2: Implement `render_radial_gradient(element, gradient_id, svg, shape_mask, final_vp_matrix)`.**
- Create a grayscale/RGBA buffer.
- Map pixels to gradient space.
- Apply `gradientTransform`.
- Interpolate colors based on distance.

**Step 3: Update `apply_fill` to handle `url(#...)` and call `render_radial_gradient`.**

**Step 4: Create a test SVG and verify radial gradient rendering.**

**Step 5: Commit.**

```bash
git add src/light_map/rendering/svg/renderer.py
git commit -m "feat: implement radial gradient rendering"
```

### Task 4: Implement Masking Support

**Files:**
- Modify: `src/light_map/rendering/svg/loader.py`
- Modify: `src/light_map/rendering/svg/renderer.py`

**Step 1: Update `SVGLoader._render_internal` to detect `mask` attribute.**

**Step 2: Implement a way to render an element (and its children) into a temporary buffer.**

**Step 3: Implement `render_mask(mask_id, svg, width, height, final_vp_matrix)`.**
- Traverse and render the children of the mask group into a grayscale image.

**Step 4: Combine element buffer with mask buffer using alpha multiplication.**

**Step 5: Create a test SVG and verify masking.**

**Step 6: Commit.**

```bash
git add src/light_map/rendering/svg/
git commit -m "feat: implement SVG masking support"
```

### Task 5: Final Verification with `fortunes-hart-space.svg`

**Step 1: Render `maps/fortunes-hart-space.svg` and verify visual correctness.**

**Step 2: Commit.**

```bash
git commit -m "docs: confirm SVG feature implementation for fortunes-hart-space.svg"
```
