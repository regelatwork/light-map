import numpy as np
from light_map.renderer import Renderer
from light_map.common_types import Layer, LayerMode, ImagePatch
from light_map.core.world_state import WorldState
from typing import List, Optional


class MockLayer(Layer):
    def __init__(
        self,
        state: Optional[WorldState] = None,
        mode: LayerMode = LayerMode.NORMAL,
        patches: Optional[List[ImagePatch]] = None,
        is_static: bool = False,
    ):
        super().__init__(state=state, is_static=is_static, layer_mode=mode)
        self.patches = patches or []
        self._dirty = True

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _generate_patches(self) -> List[ImagePatch]:
        self._dirty = False
        return self.patches


def test_renderer_initialization():
    renderer = Renderer(800, 600)
    assert renderer.screen_width == 800
    assert renderer.screen_height == 600
    assert renderer.output_buffer.shape == (600, 800, 3)
    assert np.all(renderer.output_buffer == 0)


def test_renderer_blocking_layer():
    renderer = Renderer(100, 100)
    # Create a red patch
    red_data = np.zeros((50, 50, 4), dtype=np.uint8)
    red_data[:, :, 0:2] = 0
    red_data[:, :, 2] = 255  # BGR Red
    red_data[:, :, 3] = 255  # Opaque

    patch = ImagePatch(x=10, y=10, width=50, height=50, data=red_data)
    layer = MockLayer(mode=LayerMode.BLOCKING, patches=[patch])

    out = renderer.render(None, [layer])

    # Check a pixel inside the patch
    assert np.array_equal(out[25, 25], [0, 0, 255])
    # Check a pixel outside
    assert np.array_equal(out[5, 5], [0, 0, 0])


def test_renderer_normal_layer_alpha_blending():
    renderer = Renderer(100, 100)

    # 1. Bottom layer: Solid Blue (BLOCKING)
    blue_data = np.zeros((100, 100, 4), dtype=np.uint8)
    blue_data[:, :, 0] = 255  # BGR Blue
    blue_data[:, :, 3] = 255
    layer1 = MockLayer(
        mode=LayerMode.BLOCKING, patches=[ImagePatch(0, 0, 100, 100, blue_data)]
    )

    # 2. Top layer: 50% Alpha Green (NORMAL)
    green_data = np.zeros((100, 100, 4), dtype=np.uint8)
    green_data[:, :, 1] = 255  # BGR Green
    green_data[:, :, 3] = 128  # ~50% alpha
    layer2 = MockLayer(
        mode=LayerMode.NORMAL, patches=[ImagePatch(0, 0, 100, 100, green_data)]
    )

    out = renderer.render(None, [layer1, layer2])

    # Expected: 0.5 * [0, 255, 0] + 0.5 * [255, 0, 0] = [127, 127, 0] (approx)
    val = out[50, 50]
    assert 120 <= val[0] <= 135  # Blue component
    assert 120 <= val[1] <= 135  # Green component
    assert val[2] == 0  # Red component


def test_renderer_clipping():
    renderer = Renderer(100, 100)

    # 1. Patch partially off-left (x=-25, y=0, w=50, h=100)
    red_data = np.zeros((100, 50, 4), dtype=np.uint8)
    red_data[:, :, 2] = 255  # BGR Red
    red_data[:, :, 3] = 255
    layer = MockLayer(
        mode=LayerMode.BLOCKING, patches=[ImagePatch(-25, 0, 50, 100, red_data)]
    )

    out = renderer.render(None, [layer])
    # x=0 to x=24 should be red. x=25 should be black.
    assert np.array_equal(out[50, 10], [0, 0, 255])
    assert np.array_equal(out[50, 30], [0, 0, 0])

    # 2. Patch partially off-bottom (x=0, y=75, w=100, h=50)
    blue_data = np.zeros((50, 100, 4), dtype=np.uint8)
    blue_data[:, :, 0] = 255  # BGR Blue
    blue_data[:, :, 3] = 255
    layer = MockLayer(
        mode=LayerMode.BLOCKING, patches=[ImagePatch(0, 75, 100, 50, blue_data)]
    )

    out = renderer.render(None, [layer])
    # y=75 to y=99 should be blue.
    assert np.array_equal(out[90, 50], [255, 0, 0])
    # y=70 should be black
    assert np.array_equal(out[70, 50], [0, 0, 0])


def test_renderer_skip_if_not_dirty():
    renderer = Renderer(100, 100)
    state = WorldState()
    layer = MockLayer(state=state)

    # Initial render
    frame = renderer.render(state, [layer])
    assert frame is not None

    # Subsequent render without changes should return None
    frame = renderer.render(state, [layer])
    assert frame is None

    # Set dirty again
    layer._dirty = True
    frame = renderer.render(state, [layer])
    assert frame is not None
