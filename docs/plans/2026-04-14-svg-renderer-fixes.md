# SVG Renderer Fixes Plan - Progress & Next Steps

**Goal:** Resolve issues in the SVG renderer where gradients and masked elements were rendered incorrectly (black/grey or invisible).

## Progress (2026-04-14) - COMPLETE

### 1. SVG Library Patches (`svgelements.py`)
- **Tag Preservation:** Fixed a bug where the `tag` attribute was not being stored in the `values` dictionary for generic `SVGElement` objects (e.g., `<stop>`), causing gradient stop resolution to fail.
- **Nested Structure Capture:** Updated the parser to treat `mask`, `radialGradient`, and `linearGradient` as `Group` objects. This allows the renderer to access their children (like gradient stops) while maintaining the correct element hierarchy.
- **Context Management:** Fixed a bug in the patch where newly created `Group` elements were not properly appended to their parent context, causing them to be orphaned and unfindable via `get_element_by_id`.

### 2. Gradient Rendering Improvements (`renderer.py`)
- **Matrix Multiplication Order:** Corrected the order of operations when mapping screen pixels back to gradient space. Used `~(g_transform * final_vp_matrix)` to ensure transformations are applied in the standard SVG order.
- **Inherited Transforms:** Added support for inherited transforms (e.g., the mm-to-pixel scaling on the root SVG element) by incorporating the element's `transform` attribute into the `g_transform` matrix.
- **Radial Focal Points:** Added handling for `fx` and `fy` (focal points) in radial gradients.

### 3. Masking & Blending Support
- **BGRA Utility:** Implemented a robust `blend_bgra` function in `renderer.py` that handles alpha compositing for both BGR and BGRA target buffers.
- **4-Channel Buffers:** Updated `render_image_element`, `apply_fill`, and `apply_stroke` to detect and handle 4-channel buffers correctly, preventing NumPy broadcasting errors and ensuring proper transparency.
- **Mask Buffer Isolation:** Refactored `loader.py` to render masked subtrees into an isolated 4-channel buffer before compositing them with the mask's alpha channel.

---

## Verification
- Ran comprehensive rendering tests on `maps/fortunes-hart-space.svg`.
- Confirmed that gradients render with the correct colors (rather than black).
- Confirmed that masked images are properly composited (rather than flat grey).
- Cleaned up all temporary debug and verification files.
