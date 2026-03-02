from light_map.menu_layer import MenuLayer
from light_map.core.world_state import WorldState
from light_map.menu_system import MenuState, MenuItem


def get_default_menu_state(**kwargs):
    defaults = {
        "current_menu_title": "Main",
        "active_items": [],
        "item_rects": [],
        "hovered_item_index": None,
        "feedback_item_index": None,
        "prime_progress": 0.0,
        "summon_progress": 0.0,
        "just_triggered_action": None,
        "cursor_pos": None,
        "is_visible": True,
    }
    defaults.update(kwargs)
    return MenuState(**defaults)


def test_menu_layer_render_visible():
    ws = WorldState()
    items = [MenuItem(title="Item 1")]
    rects = [(10, 10, 100, 50)]
    ws.update_menu_state(
        get_default_menu_state(active_items=items, item_rects=rects, is_visible=True)
    )

    layer = MenuLayer()
    patches = layer.render(ws)

    assert len(patches) == 1
    patch = patches[0]
    assert patch.x == 10
    assert patch.y == 10
    assert patch.width == 100
    assert patch.height == 50
    assert patch.data.shape == (50, 100, 4)


def test_menu_layer_render_hidden():
    ws = WorldState()
    ws.update_menu_state(get_default_menu_state(is_visible=False))

    layer = MenuLayer()
    patches = layer.render(ws)
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

    layer = MenuLayer()
    layer.render(ws)
    assert layer.last_rendered_timestamp == ws.menu_timestamp

    old_ts = layer.last_rendered_timestamp
    # Render again without change
    layer.render(ws)
    assert layer.last_rendered_timestamp == old_ts

    # Render after change
    ws.increment_menu_timestamp()
    layer.render(ws)
    assert layer.last_rendered_timestamp > old_ts
