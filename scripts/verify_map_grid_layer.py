import os
import sys
import numpy as np

# Add src to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from light_map.state.world_state import WorldState
from light_map.rendering.layers.map_grid_layer import MapGridLayer
from light_map.core.common_types import GridMetadata, ViewportState


def verify_map_grid_layer():
    print("Initializing WorldState...")
    state = WorldState()

    # Task 8: Simulate a WorldState update
    print("Setting GridMetadata and ViewportState...")
    # Initialize metadata objects as requested
    grid = GridMetadata(spacing_svg=100.0, origin_svg_x=0.0, origin_svg_y=0.0)
    vp = ViewportState(x=0.0, y=0.0, zoom=1.0, rotation=0.0)

    # Set properties directly on WorldState as requested
    state.grid_spacing_svg = grid.spacing_svg
    state.grid_origin_svg_x = grid.origin_svg_x
    state.grid_origin_svg_y = grid.origin_svg_y
    state.viewport = vp

    width, height = 1920, 1080
    print(f"Initializing MapGridLayer with resolution {width}x{height}...")
    layer = MapGridLayer(state, width, height)

    print("Rendering layer...")
    patches, version = layer.render()

    if not patches:
        print("FAILED: No patches generated.")
        sys.exit(1)

    print(f"SUCCESS: Generated {len(patches)} patch(es) for version {version}.")

    for i, patch in enumerate(patches):
        print(
            f"Patch {i}: x={patch.x}, y={patch.y}, width={patch.width}, height={patch.height}"
        )
        if patch.data is None:
            print(f"FAILED: Patch {i} data is None.")
            sys.exit(1)
        if patch.data.shape != (height, width, 4):
            print(
                f"FAILED: Patch {i} data shape {patch.data.shape} does not match expected ({height}, {width}, 4)."
            )
            sys.exit(1)

        # Check if anything was drawn (should not be all zeros)
        if np.all(patch.data == 0):
            print(f"FAILED: Patch {i} data is empty (all zeros).")
            sys.exit(1)

        print(f"Patch {i} contains non-zero data, rendering appears successful.")


if __name__ == "__main__":
    try:
        verify_map_grid_layer()
        print("\nVerification script completed successfully.")
    except Exception as e:
        print(f"\nVerification script failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
