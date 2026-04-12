import numpy as np
from light_map.core.common_types import Layer, ImagePatch, CompositeLayer, LayerMode


class MockLayer(Layer):
    def __init__(self, version, patches, mode=LayerMode.NORMAL):
        super().__init__(state=None, is_static=True, layer_mode=mode)
        self._mock_version = version
        self._mock_patches = patches
        self.render_call_count = 0

    def get_current_version(self) -> int:
        return self._mock_version

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        self.render_call_count += 1
        return self._mock_patches


def test_composite_layer_versioning():
    l1 = MockLayer(1, [])
    l2 = MockLayer(2, [])
    comp = CompositeLayer([l1, l2])

    assert comp.get_current_version() == 2

    l1._mock_version = 5
    assert comp.get_current_version() == 5


def test_composite_layer_empty():
    l1 = MockLayer(1, [])
    comp = CompositeLayer([l1])

    patches, version = comp.render()
    assert version == 1
    assert len(patches) == 0


def test_composite_layer_flattening():
    # Patch 1: 10x10 red square at (0,0)
    data1 = np.zeros((10, 10, 4), dtype=np.uint8)
    data1[:, :, 2] = 255  # Red
    data1[:, :, 3] = 255  # Opaque
    p1 = ImagePatch(x=0, y=0, width=10, height=10, data=data1)
    l1 = MockLayer(1, [p1])

    # Patch 2: 10x10 green square at (5,5)
    data2 = np.zeros((10, 10, 4), dtype=np.uint8)
    data2[:, :, 1] = 255  # Green
    data2[:, :, 3] = 255  # Opaque
    p2 = ImagePatch(x=5, y=5, width=10, height=10, data=data2)
    l2 = MockLayer(2, [p2])

    comp = CompositeLayer([l1, l2])

    patches, version = comp.render()
    assert version == 2
    assert len(patches) == 1

    merged = patches[0]

    # Bounding box should be (0,0) to (15,15)
    assert merged.x == 0
    assert merged.y == 0
    assert merged.width == 15
    assert merged.height == 15

    # Check a red pixel
    assert np.array_equal(merged.data[0, 0], [0, 0, 255, 255])

    # Check a green pixel
    assert np.array_equal(merged.data[10, 10], [0, 255, 0, 255])

    # Overlap pixel should be green (l2 is on top)
    assert np.array_equal(merged.data[5, 5], [0, 255, 0, 255])


def test_composite_layer_masked():
    # Background: 10x10 Blue square at (0,0)
    data_bg = np.zeros((10, 10, 4), dtype=np.uint8)
    data_bg[:, :, 0] = 255  # Blue
    data_bg[:, :, 3] = 255  # Opaque
    p_bg = ImagePatch(x=0, y=0, width=10, height=10, data=data_bg)
    l_bg = MockLayer(1, [p_bg], mode=LayerMode.NORMAL)

    # Masked: 10x10 Green square at (2,2), but only center 4x4 is opaque
    data_mask = np.zeros((10, 10, 4), dtype=np.uint8)
    data_mask[3:7, 3:7, 1] = 255  # Green
    data_mask[3:7, 3:7, 3] = 255  # Opaque
    p_mask = ImagePatch(x=0, y=0, width=10, height=10, data=data_mask)
    l_mask = MockLayer(2, [p_mask], mode=LayerMode.MASKED)

    comp = CompositeLayer([l_bg, l_mask])

    patches, version = comp.render()
    merged = patches[0]

    # Outside the mask should still be blue
    assert np.array_equal(merged.data[0, 0], [255, 0, 0, 255])
    # Inside the mask should be green
    assert np.array_equal(merged.data[5, 5], [0, 255, 0, 255])


def test_composite_layer_caching():
    l1 = MockLayer(1, [])
    comp = CompositeLayer([l1])

    # First render
    comp.render()
    assert l1.render_call_count == 1

    # Second render, version same
    comp.render()
    assert l1.render_call_count == 1

    # Update version, should render again
    l1._mock_version = 2
    comp.render()
    assert l1.render_call_count == 2
