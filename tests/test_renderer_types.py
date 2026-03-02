from light_map.common_types import ImagePatch, LayerMode, Layer
import numpy as np
import pytest


def test_image_patch_creation():
    data = np.zeros((10, 10, 4), dtype=np.uint8)
    patch = ImagePatch(x=10, y=20, width=10, height=10, data=data)
    assert patch.x == 10
    assert patch.y == 20
    assert patch.width == 10
    assert patch.height == 10
    assert patch.data.shape == (10, 10, 4)


def test_layer_mode_enum():
    assert LayerMode.NORMAL.value == "NORMAL"
    assert LayerMode.BLOCKING.value == "BLOCKING"


def test_layer_abstract_class():
    # Verify Layer is an abstract base class
    with pytest.raises(TypeError):
        Layer()

    class MockLayer(Layer):
        def render(self, state):
            return []

    layer = MockLayer()
    assert layer.render(None) == []
