import pytest
import numpy as np
from light_map.rendering.layers.door_layer import DoorLayer
from light_map.state.world_state import WorldState
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


from dataclasses import asdict
from light_map.core.common_types import GridMetadata


@pytest.fixture
def state():
    ws = WorldState()
    from light_map.core.common_types import ViewportState

    ws.update_viewport(ViewportState(x=0, y=0, zoom=1.0, rotation=0.0))
    ws.grid_metadata = GridMetadata(spacing_svg=10.0)
    return ws


def test_door_layer_init(state):
    layer = DoorLayer(state, 100, 100)
    assert layer.width == 100
    assert layer.height == 100


def test_door_layer_render_closed_door(state):
    # Add a closed door blocker
    door = VisibilityBlocker(
        id="door1",
        segments=[(10, 10), (20, 10)],
        type=VisibilityType.DOOR,
        layer_name="Door 1",
        is_open=False,
    )
    state.blockers = [asdict(door)]

    layer = DoorLayer(state, 100, 100)
    patches = layer.render(0.0)[0]

    assert len(patches) == 1
    data = patches[0].data

    # Check if we have some non-transparent pixels
    # (0, 255, 255) is Yellow, (0, 0, 0) is Black
    # Alpha should be 255 for rendered parts
    mask = data[:, :, 3] == 255
    assert np.any(mask)

    # Check for yellow-ish color
    # (0, 255, 255) is Yellow. Let's check for pixels where Red is low and Green/Blue are high.
    yellow_ish = (data[:, :, 0] < 50) & (data[:, :, 1] > 200) & (data[:, :, 2] > 200)
    assert np.any(yellow_ish)

    # Check for black-ish color (0, 0, 0)
    black_ish = (
        (data[:, :, 0] < 50)
        & (data[:, :, 1] < 50)
        & (data[:, :, 2] < 50)
        & (data[:, :, 3] == 255)
    )
    assert np.any(black_ish)


def test_door_layer_render_open_door(state):
    # Add an open door blocker
    door = VisibilityBlocker(
        id="door2",
        segments=[(10, 10), (20, 10)],
        type=VisibilityType.DOOR,
        layer_name="Door 1",
        is_open=True,
    )
    state.blockers = [asdict(door)]

    layer = DoorLayer(state, 100, 100)
    patches = layer.render(0.0)[0]

    assert len(patches) == 1
    data = patches[0].data

    # Check if we have non-transparent pixels
    mask = data[:, :, 3] == 255
    assert np.any(mask)

    # Check for yellow circles at (10, 10) and (20, 10)
    # Since it's a 100x100 buffer with 1:1 zoom, center should be (50, 50) for (0,0) SVG?
    # Wait, in DoorLayer:
    # m_svg_to_screen.post_scale(vp.zoom, vp.zoom)
    # m_svg_to_screen.post_rotate(math.radians(vp.rotation), cx, cy)
    # m_svg_to_screen.post_translate(vp.x, vp.y)

    # (10, 10) -> (10, 10) if zoom=1, rot=0, x=0, y=0?
    # NO, rotation is around cx, cy (50, 50).
    # If rotation is 0, it should be fine.

    assert data[10, 10, 3] == 255
    assert np.all(data[10, 10, :3] == [0, 255, 255])

    assert data[10, 20, 3] == 255  # Wait, segments are (x, y) so (20, 10)
    assert data[10, 20, 3] == 255  # wait data is [y, x]
    assert data[10, 20, 3] == 255
    assert np.all(data[10, 20, :3] == [0, 255, 255])


def test_door_layer_version_logic(state):
    layer = DoorLayer(state, 100, 100)

    # Initial state
    v1 = layer.get_current_version()
    patches, rv1 = layer.render(0.0)
    assert rv1 == v1

    # Subsequent render should return same version, no re-render needed
    patches, rv2 = layer.render(0.0)
    assert rv2 == v1

    # Update visibility version - use data mutation
    state.visibility_mask = np.zeros((100, 100), dtype=np.uint8)
    v2 = layer.get_current_version()
    assert v2 > v1
    patches, rv3 = layer.render(0.0)
    assert rv3 == v2

    # Update viewport
    from light_map.core.common_types import ViewportState

    # Update viewport to trigger new version
    state.update_viewport(ViewportState(x=100, y=100, zoom=2.0, rotation=45.0))
    v3 = layer.get_current_version()
    assert v3 > v2
