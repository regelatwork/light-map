import numpy as np
from light_map.renderer import Renderer
from light_map.common_types import ImagePatch, Layer


class MockLayer(Layer):
    def __init__(self, color, alpha, is_static=False):
        super().__init__(is_static=is_static)
        self.color = color
        self.alpha = alpha
        self._is_dirty = True

    @property
    def is_dirty(self):
        return self._is_dirty

    def _generate_patches(self, current_time: float = 0.0):
        data = np.zeros((100, 100, 4), dtype=np.uint8)
        data[:, :, :3] = self.color
        data[:, :, 3] = self.alpha
        self._is_dirty = False
        return [ImagePatch(0, 0, 100, 100, data)]


def test_renderer_visibility_composition():
    renderer = Renderer(100, 100)

    # Layer 1: Base Map (Solid Red BGR: 0, 0, 255)
    map_layer = MockLayer((0, 0, 255), 255, is_static=True)

    # Layer 2: FoW (Exploration Memory)
    # (0,0) to (50,100) is Unexplored (Alpha 255)
    # (50,0) to (100,100) is Explored (Alpha 0)
    fow_data = np.zeros((100, 100, 4), dtype=np.uint8)
    fow_data[:, :50, 3] = 255  # Unexplored
    fow_data[:, 50:, 3] = 0  # Explored

    class FowLayer(Layer):
        @property
        def is_dirty(self):
            return True

        def _generate_patches(self, current_time: float = 0.0):
            return [ImagePatch(0, 0, 100, 100, fow_data)]

    fow_layer = FowLayer()

    # Layer 3: Visibility (Active LOS Shroud)
    # (0,0) to (75,100) is NOT Visible (Alpha 150)
    # (75,0) to (100,100) is Visible (Alpha 0)
    vis_data = np.zeros((100, 100, 4), dtype=np.uint8)
    vis_data[:, :75, 3] = 150  # Not Visible (Shroud)
    vis_data[:, 75:, 3] = 0  # Visible

    class VisLayer(Layer):
        @property
        def is_dirty(self):
            return True

        def _generate_patches(self, current_time: float = 0.0):
            return [ImagePatch(0, 0, 100, 100, vis_data)]

    vis_layer = VisLayer()

    frame = renderer.render(None, [map_layer, fow_layer, vis_layer])

    # 1. Check Unexplored area (x < 50)
    # Should be BLACK (0,0,0) regardless of visibility
    assert np.all(frame[50, 10] == [0, 0, 0])

    # 2. Check Explored but NOT Visible area (50 <= x < 75)
    # Should be DIMMED RED
    # Red is (0, 0, 255).
    # Alpha 150 (approx 60% opaque black) -> approx 40% of original color.
    # 255 * (1 - 150/255) = 255 * 0.41 = 105
    assert 100 <= frame[50, 60][2] <= 110
    assert frame[50, 60][0] == 0
    assert frame[50, 60][1] == 0

    # 3. Check Visible area (x >= 75)
    # Should be FULL BRIGHT RED
    assert np.all(frame[50, 80] == [0, 0, 255])
