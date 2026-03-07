# SVG Loader Library

This package provides a modular and high-performance SVG parsing and rendering system for the Light Map project. It is designed to handle complex map files exported from Inkscape, supporting both visual rendering and geometric extraction for the visibility engine.

## Public API

The primary entry point is the `SVGLoader` class, which is exported in the top-level `light_map.svg` package.

```python
from light_map.svg import SVGLoader

# Initialize with an SVG file
loader = SVGLoader("maps/dungeon.svg")

# Render to an OpenCV BGR buffer
# Parameters: width, height, zoom, offset_x, offset_y, rotation, quality
image = loader.render(1920, 1080, scale_factor=1.5, quality=0.5)

# Extract geometric blockers for the Visibility Engine
# Returns a list of VisibilityBlocker objects
blockers = loader.get_visibility_blockers()

# Detect grid spacing and origin from SVG geometry
spacing, origin_x, origin_y = loader.detect_grid_spacing()
```

## Features

- **Adaptive Curve Sampling**: Bezier curves and Arcs are sampled dynamically based on their length and the current zoom level, ensuring smooth shadows and rendering.
- **Opacity & Transparency**: Full support for `opacity`, `fill-opacity`, and `stroke-opacity` using OpenCV alpha blending.
- **Dashed Lines**: Support for `stroke-dasharray` with automatic scaling.
- **Symbols & Clones**: Support for `<symbol>` and `<use>` elements, enabling efficient reuse of map assets.
- **Layer-based Extraction**: Automatically identifies Walls, Doors, and Windows based on Inkscape layer labels or element IDs.

## Internal Organization

The library is split into specialized modules to maintain low cyclomatic complexity and high readability:

- **`loader.py`**: The `SVGLoader` facade. Handles high-level orchestration, caching (`lru_cache`), and recursive element traversal.
- **`renderer.py`**: Implementation of specialized renderers for Shapes, Text, and Raster Images. Manages OpenCV drawing calls and alpha blending.
- **`geometry.py`**: Geometric algorithms including adaptive curve sampling, path-to-points conversion, and grid detection heuristics.
- **`blockers.py`**: Logic for extracting `VisibilityBlocker` metadata from SVG hierarchies.
- **`utils.py`**: Helper functions for attribute extraction (IDs, labels, opacity) and transformation matrix math.

## Maintenance

All methods in this library are strictly enforced to have a **Cyclomatic Complexity < 10**. When adding new features (e.g., Gradients, Filter support), ensure that logic is decomposed into helper methods or new modules rather than expanding existing functions.
