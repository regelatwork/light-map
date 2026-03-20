from unittest.mock import MagicMock
import numpy as np
from light_map.selection_progress_layer import SelectionProgressLayer
from light_map.core.world_state import WorldState
from light_map.core.scene import HandInput


def test_selection_progress_layer_render_no_hands():
    ws = WorldState()
    context = MagicMock()
    layer = SelectionProgressLayer(ws, context)
    ws.inputs = []
    assert len(layer.render()[0]) == 0


def test_selection_progress_layer_render_with_progress():
    ws = WorldState()
    context = MagicMock()
    layer = SelectionProgressLayer(ws, context)

    hand = MagicMock(spec=HandInput)
    hand.cursor_pos = (500, 500)
    ws.inputs = [hand]
    ws.dwell_state = {
        "target_id": "token1",
        "accumulated_time": 1.0,
        "dwell_time_threshold": 2.0,
    }
    ws.summon_progress = 0.5
    ws.hands_timestamp = 2

    patches = layer.render()[0]
    assert len(patches) == 1
    p = patches[0]
    # ring_radius is 16, buffer is ring_radius*2 + 6 = 38
    assert p.width == 38
    assert p.height == 38
    assert p.x == 500 - 19
    assert p.y == 500 - 19
    assert np.any(p.data > 0)


def test_selection_progress_layer_no_progress():
    ws = WorldState()
    context = MagicMock()
    layer = SelectionProgressLayer(ws, context)

    hand = MagicMock(spec=HandInput)
    hand.cursor_pos = (500, 500)
    ws.inputs = [hand]
    ws.dwell_state = {}
    ws.summon_progress = 0.0
    ws.hands_timestamp = 2

    patches = layer.render()[0]
    assert len(patches) == 0
