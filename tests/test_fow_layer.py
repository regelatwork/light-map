import numpy as np
from light_map.rendering.layers.fow_layer import FogOfWarLayer
from light_map.visibility.fow_manager import FogOfWarManager


from light_map.state.world_state import WorldState


def test_fow_initialization():
    ws = WorldState()
    layer = FogOfWarLayer(ws, 100, 100)
    assert layer.width == 100
    assert layer.height == 100
    assert layer.get_current_version() > 0


def test_fow_render_two_states():
    ws = WorldState()
    layer = FogOfWarLayer(ws, 10, 10)

    # 1. Unexplored (All black/opaque)
    # Set empty fow_mask to trigger it
    ws.fow_mask = np.zeros((10, 10), dtype=np.uint8)

    # Set grid metadata so transformation works
    from light_map.core.common_types import GridMetadata
    ws.grid_metadata = GridMetadata(spacing_svg=16.0)

    patches = layer.render()[0]
    alpha = patches[0].data[:, :, 3]
    assert np.all(alpha == 255)

    # 2. Explored (Transparent)
    # The current implementation treats Explored as 0 alpha (Transparent)
    # because VisibilityLayer handles the "dimming" of non-visible areas.
    explored = np.zeros((10, 10), dtype=np.uint8)
    explored[0, 0] = 255
    ws.fow_mask = explored

    patches = layer.render()[0]
    alpha = patches[0].data[:, :, 3]
    assert alpha[0, 0] == 0
    assert alpha[1, 1] == 255


def test_fow_rendering_with_non_zero_origin():
    # Grid origin at (100, 100)
    ws = WorldState()
    # Mask is 10x10. Spacing 16.0 means 16px per grid unit.
    # FogOfWarLayer scale is spacing / 16.0 = 1.0.
    spacing = 16.0
    layer = FogOfWarLayer(ws, 200, 200)

    # Explored at (5, 5) in mask space
    explored = np.zeros((10, 10), dtype=np.uint8)
    explored[5, 5] = 255
    ws.fow_mask = explored

    # Set grid metadata so transformation works
    from light_map.core.common_types import GridMetadata
    ws.grid_metadata = GridMetadata(spacing_svg=spacing, origin_svg_x=100.0, origin_svg_y=100.0)

    # Viewport at zoom=1.0, no offset
    from light_map.core.common_types import ViewportState

    ws.update_viewport(ViewportState(x=0, y=0, zoom=1.0, rotation=0))

    patches = layer.render()[0]
    data = patches[0].data

    # Transformation: p_screen = m_svg_to_screen * m_fow_to_svg * p_fow
    # m_fow_to_svg = Scale(1) * Translate(0) [after fix]
    # m_svg_to_screen = Scale(1) * Rotate(0, 100, 100) * Translate(0) = Identity
    # So (5,5) in mask should be at (5,5) on screen.

    # Wait, screen center cx, cy = 100, 100
    # Identity transform should map (5,5) to (5,5).

    assert data[5, 5, 3] == 0  # Transparent
    assert data[0, 0, 3] == 255  # Opaque (unexplored)


def test_fow_gm_override():
    ws = WorldState()
    layer = FogOfWarLayer(ws, 10, 10)
    ws.fow_mask = np.zeros((10, 10), dtype=np.uint8)
    ws.fow_disabled = True

    patches = layer.render()[0]
    # No patches should be returned when disabled
    assert len(patches) == 0
