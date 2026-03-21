from light_map.core.world_state import WorldState
from light_map.common_types import ViewportState

def test_viewport_is_atomic():
    state = WorldState()
    assert hasattr(state, "_viewport_atom")
    assert isinstance(state.viewport, ViewportState)

def test_update_viewport_updates_atom():
    state = WorldState()
    new_vp = ViewportState(x=100)
    state.update_viewport(new_vp)
    assert state.viewport.x == 100
    assert state.viewport_timestamp == state._viewport_atom.timestamp

def test_menu_state_is_atomic():
    state = WorldState()
    assert hasattr(state, "_menu_state_atom")
    assert state.menu_state is None

def test_update_menu_state_updates_atom():
    from light_map.menu_system import MenuState
    state = WorldState()
    # Provide required arguments for MenuState
    new_menu = MenuState(
        current_menu_title="test",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        just_triggered_action=None,
        cursor_pos=None,
        is_visible=True,
        node_stack_titles=[],
        debug_info=""
    )
    state.update_menu_state(new_menu)
    assert state.menu_state == new_menu
    assert state.menu_timestamp == state._menu_state_atom.timestamp

