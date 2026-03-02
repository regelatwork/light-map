import numpy as np
from light_map.renderer import Renderer
from light_map.common_types import Layer, LayerMode, ImagePatch


class MockLayer(Layer):
    def __init__(self, mode=LayerMode.NORMAL, patches=None):
        super().__init__(layer_mode=mode)
        self.patches = patches or []

    def render(self, state):
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
    red_data[:, :, 0:3] = [0, 0, 255]  # BGR Red
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
    blue_data[:, :, 0:3] = [255, 0, 0]  # BGR Blue
    blue_data[:, :, 3] = 255
    layer1 = MockLayer(
        mode=LayerMode.BLOCKING, patches=[ImagePatch(0, 0, 100, 100, blue_data)]
    )

    # 2. Top layer: 50% Alpha Green (NORMAL)
    green_data = np.zeros((100, 100, 4), dtype=np.uint8)
    green_data[:, :, 0:3] = [0, 255, 0]  # BGR Green
    green_data[:, :, 3] = 128  # ~50% alpha
    layer2 = MockLayer(
        mode=LayerMode.NORMAL, patches=[ImagePatch(0, 0, 100, 100, green_data)]
    )

    out = renderer.render(None, [layer1, layer2])

    # Expected: 0.5 * [0, 255, 0] + 0.5 * [255, 0, 0] = [127, 127, 0] (approx)
    # Actually: (0, 127, 127) because 128/255 is ~0.5019
    # Blue: 255 * (1 - 0.5019) = 127.01
    # Green: 255 * 0.5019 = 127.98
    # So [127, 128, 0] is likely
    val = out[50, 50]
    assert 120 <= val[0] <= 135  # Blue component
    assert 120 <= val[1] <= 135  # Green component
    assert val[2] == 0  # Red component
