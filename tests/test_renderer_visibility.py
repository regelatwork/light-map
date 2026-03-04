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

    def _generate_patches(self):
        data = np.zeros((100, 100, 4), dtype=np.uint8)
        data[:, :, :3] = self.color
        data[:, :, 3] = self.alpha
        self._is_dirty = False
        return [ImagePatch(0, 0, 100, 100, data)]


def test_renderer_visibility_composition():
    renderer = Renderer(100, 100)

    # Layer 1: Base Map (Solid Red)
    map_layer = MockLayer((0, 0, 255), 255, is_static=True)

    # Layer 2: FoW (Black with holes)
    # Let's simulate:
    # (0,0) to (50,100) is Unexplored (Alpha 255)
    # (50,0) to (100,100) is Explored (Alpha 178)
    fow_data = np.zeros((100, 100, 4), dtype=np.uint8)
    fow_data[:, :50, 3] = 255  # Unexplored
    fow_data[:, 50:, 3] = 178  # Explored (dimmed)

    class FowLayer(Layer):
        @property
        def is_dirty(self):
            return True

        def _generate_patches(self):
            return [ImagePatch(0, 0, 100, 100, fow_data)]

    fow_layer = FowLayer()

    # Layer 3: Visibility (LOS Hole)
    # Circle at (75, 50) is Visible (Alpha 0)
    vis_data = np.zeros((100, 100, 4), dtype=np.uint8)
    vis_data.fill(0)  # Transparent everywhere else?
    # Actually FoWLayer handles the blacking out.
    # VisibilityLayer in my implementation adds a BLUE tint.
    # Let's just test FoWLayer composition first as it's the primary blocker.

    frame = renderer.render(None, [map_layer, fow_layer])

    # Check pixels
    # Unexplored area (0, 50) should be BLACK (0,0,0)
    assert np.all(frame[50, 10] == [0, 0, 0])

    # Explored area (75, 50) should be DIMMED RED
    # Red is (0, 0, 255).
    # Alpha 178 (70% opaque black) -> 30% of original color.
    # 255 * 0.3 = 76.5
    assert 70 <= frame[50, 75][2] <= 85
    assert frame[50, 75][0] == 0
    assert frame[50, 75][1] == 0
