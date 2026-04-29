from unittest.mock import MagicMock

from light_map.core.common_types import GestureType
from light_map.core.scene import HandInput
from light_map.rendering.layers.cursor_layer import CursorLayer
from light_map.state.world_state import WorldState


def test_cursor_layer_initialization():
    ws = WorldState()
    context = MagicMock()
    layer = CursorLayer(ws, context)
    assert layer.get_current_version() > 0


def test_cursor_layer_render_no_hands():
    ws = WorldState()
    context = MagicMock()
    layer = CursorLayer(ws, context)
    ws.inputs = []
    assert len(layer.render()[0]) == 0


def test_cursor_layer_render_with_cursor():
    ws = WorldState()
    context = MagicMock()
    layer = CursorLayer(ws, context)

    # Mock HandInput with cursor_pos
    hand = MagicMock(spec=HandInput)
    hand.gesture = GestureType.POINTING
    hand.cursor_pos = (500, 500)
    ws.inputs = [hand]  # Triggers hands_version change

    patches = layer.render()[0]
    assert len(patches) == 1
    p = patches[0]
    # Reticle should be centered at (500, 500)
    # Radius is 12, buffer is radius*2 + 4 = 28
    assert p.x == 500 - 14
    assert p.y == 500 - 14
    assert p.width == 28
    assert p.height == 28


def test_cursor_layer_render_without_cursor():
    ws = WorldState()
    context = MagicMock()
    layer = CursorLayer(ws, context)

    # Mock HandInput with NONE gesture (no cursor_pos)
    hand = MagicMock(spec=HandInput)
    hand.gesture = GestureType.NONE
    hand.cursor_pos = None
    ws.inputs = [hand]  # Triggers hands_version change

    patches = layer.render()[0]
    assert len(patches) == 0
