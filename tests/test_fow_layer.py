import numpy as np
from light_map.fow_layer import FogOfWarLayer
from light_map.fow_manager import FogOfWarManager


from light_map.core.world_state import WorldState


def test_fow_initialization():
    ws = WorldState()
    manager = FogOfWarManager(100, 100)
    layer = FogOfWarLayer(ws, manager, 10.0, (0.0, 0.0), 100, 100)
    assert layer.manager.width == 100
    assert layer.manager.height == 100
    assert layer.get_current_version() > 0


def test_fow_render_two_states():
    ws = WorldState()
    manager = FogOfWarManager(10, 10)
    layer = FogOfWarLayer(ws, manager, 10.0, (0.0, 0.0), 10, 10)

    # 1. Unexplored (All black/opaque)
    patches = layer.render()[0]
    alpha = patches[0].data[:, :, 3]
    assert np.all(alpha == 255)

    # 2. Explored (Transparent)
    # The current implementation treats Explored as 0 alpha (Transparent)
    # because VisibilityLayer handles the "dimming" of non-visible areas.
    explored = np.zeros((10, 10), dtype=np.uint8)
    explored[0, 0] = 255
    manager.reveal_area(explored)
    ws.increment_fow_timestamp()

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
    manager = FogOfWarManager(10, 10)  # 10x10 pixels
    layer = FogOfWarLayer(ws, manager, spacing, (100.0, 100.0), 200, 200)

    # Explored at (5, 5) in mask space
    explored = np.zeros((10, 10), dtype=np.uint8)
    explored[5, 5] = 255
    manager.reveal_area(explored)
    ws.increment_fow_timestamp()

    # Viewport at zoom=1.0, no offset
    from light_map.common_types import ViewportState

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
    manager = FogOfWarManager(10, 10)
    layer = FogOfWarLayer(ws, manager, 10.0, (0.0, 0.0), 10, 10)
    manager.is_disabled = True
    ws.increment_fow_timestamp()

    patches = layer.render()[0]
    # No patches should be returned when disabled
    assert len(patches) == 0
