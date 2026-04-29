
import numpy as np

from light_map.core.common_types import AppConfig, ImagePatch, Layer, LayerMode
from light_map.rendering.renderer import Renderer
from light_map.state.world_state import WorldState


class MockLayer(Layer):
    def __init__(
        self,
        state: WorldState | None = None,
        mode: LayerMode = LayerMode.NORMAL,
        patches: list[ImagePatch] | None = None,
        is_static: bool = False,
    ):
        super().__init__(state=state, is_static=is_static, layer_mode=mode)
        self.patches = patches or []
        self._version = 1

    def get_current_version(self) -> int:
        return self._version

    def _generate_patches(self, current_time: float = 0.0) -> list[ImagePatch]:
        return self.patches


def test_renderer_initialization():
    config = AppConfig(width=800, height=600, projector_matrix=np.eye(3))
    renderer = Renderer(config)
    assert renderer.screen_width == 800
    assert renderer.screen_height == 600
    assert renderer.output_buffer.shape == (600, 800, 3)
    assert np.all(renderer.output_buffer == 0)


def test_renderer_blocking_layer():
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)
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
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)

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
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)

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


def test_renderer_skip_if_version_unchanged():
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)
    state = WorldState()
    layer = MockLayer(state=state)

    # Initial render
    frame = renderer.render(state, [layer])
    assert frame is not None

    # Subsequent render without version changes should return None (skipped)
    frame = renderer.render(state, [layer])
    assert frame is None

    # Trigger re-render by incrementing version
    layer._version += 1
    frame = renderer.render(state, [layer])
    assert frame is not None


def test_renderer_layer_stack_change_invalidates_cache():
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)
    state = WorldState()

    # 1. First stack: Blue layer
    blue_data = np.zeros((100, 100, 4), dtype=np.uint8)
    blue_data[:, :, 0] = 255
    blue_data[:, :, 3] = 255
    layer1 = MockLayer(patches=[ImagePatch(0, 0, 100, 100, blue_data)], is_static=True)

    out1 = renderer.render(state, [layer1])
    assert np.array_equal(out1[0, 0], [255, 0, 0])

    # 2. Second stack: Red layer (replaces Blue)
    red_data = np.zeros((100, 100, 4), dtype=np.uint8)
    red_data[:, :, 2] = 255
    red_data[:, :, 3] = 255
    layer2 = MockLayer(patches=[ImagePatch(0, 0, 100, 100, red_data)], is_static=True)

    out2 = renderer.render(state, [layer2])
    # If cache wasn't invalidated, this might still be blue
    assert np.array_equal(out2[0, 0], [0, 0, 255])
