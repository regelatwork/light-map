import numpy as np
from light_map.menu_layer import MenuLayer
from light_map.common_types import MenuItem
from light_map.menu_system import MenuState
from light_map.core.world_state import WorldState


def get_default_menu_state(
    active_items=None, item_rects=None, is_visible=True, hovered=None, feedback=None
):
    return MenuState(
        current_menu_title="Root",
        active_items=active_items or [],
        item_rects=item_rects or [],
        is_visible=is_visible,
        hovered_item_index=hovered,
        feedback_item_index=feedback,
        prime_progress=0.0,
        summon_progress=0.0,
        just_triggered_action=None,
        cursor_pos=None,
    )


def test_menu_layer_render_visible():
    ws = WorldState()
    items = [MenuItem(title="Item 1")]
    rects = [(10, 10, 100, 50)]
    ws.update_menu_state(
        get_default_menu_state(active_items=items, item_rects=rects, is_visible=True)
    )

    layer = MenuLayer(ws)
    patches = layer.render()

    assert len(patches) == 1
    p = patches[0]
    assert p.x == 10
    assert p.y == 10
    assert p.width == 100
    assert p.height == 50
    assert p.data.shape == (50, 100, 4)


def test_menu_layer_render_hidden():
    ws = WorldState()
    ws.update_menu_state(get_default_menu_state(is_visible=False))

    layer = MenuLayer(ws)
    patches = layer.render()
    assert len(patches) == 0


def test_menu_layer_caching():
    ws = WorldState()
    ws.update_menu_state(
        get_default_menu_state(
            active_items=[MenuItem(title="Item 1")],
            item_rects=[(0, 0, 100, 50)],
            is_visible=True,
        )
    )

    layer = MenuLayer(ws)
    p1 = layer.render()
    p2 = layer.render()

    # Should be the same list object due to caching
    assert p1 is p2

    # Change timestamp
    ws.increment_menu_timestamp()
    p3 = layer.render()
    assert p3 is not p1  # New list
    assert len(p3) == 1
