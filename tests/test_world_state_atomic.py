from light_map.state.world_state import WorldState
from light_map.core.common_types import ViewportState


def test_viewport_is_atomic():
    state = WorldState()
    assert hasattr(state, "_viewport_atom")
    assert isinstance(state.viewport, ViewportState)


def test_update_viewport_updates_atom():
    state = WorldState()
    new_vp = ViewportState(x=100)
    state.update_viewport(new_vp)
    assert state.viewport.x == 100
    assert state.viewport_version == state._viewport_atom.timestamp


def test_menu_state_is_atomic():
    state = WorldState()
    assert hasattr(state, "_menu_state_atom")
    assert state.menu_state is None


def test_update_menu_state_updates_atom():
    from light_map.menu.menu_system import MenuState

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
        debug_info="",
    )
    state.update_menu_state(new_menu)
    assert state.menu_state == new_menu
    assert state.menu_version == state._menu_state_atom.timestamp


def test_dwell_state_and_summon_progress_are_atomic():
    import time

    state = WorldState()

    # Initial timestamps
    ts1_dwell = state.dwell_state_version
    ts1_summon = state.summon_progress_version

    # Sleep a bit to ensure monotonic clock advances enough if needed (though monotonic_ns should advance)
    time.sleep(0.001)

    # Update dwell_state
    state.dwell_state = {"test": 1}
    assert state.dwell_state == {"test": 1}
    assert state.dwell_state_version > ts1_dwell

    # Update summon_progress
    state.summon_progress = 0.5
    assert state.summon_progress == 0.5
    assert state.summon_progress_version > ts1_summon

    # Verify no update if same value
    ts2_dwell = state.dwell_state_version
    state.dwell_state = {"test": 1}
    assert state.dwell_state_version == ts2_dwell


def test_selection_and_grid_metadata_are_atomic():
    import time
    from light_map.core.common_types import SelectionState, SelectionType, GridMetadata

    state = WorldState()

    # Initial timestamps
    ts1_selection = state.selection_version
    ts1_grid = state.grid_metadata_version

    time.sleep(0.001)

    # Update selection
    state.selection = SelectionState(type=SelectionType.TOKEN, id="42")
    assert state.selection.type == SelectionType.TOKEN
    assert state.selection.id == "42"
    assert state.selection_version > ts1_selection

    # Update grid metadata
    state.grid_metadata = GridMetadata(spacing_svg=50.0)
    assert state.grid_metadata.spacing_svg == 50.0
    assert state.grid_metadata_version > ts1_grid

    # Verify no update if same value
    ts2_selection = state.selection_version
    state.selection = SelectionState(type=SelectionType.TOKEN, id="42")
    assert state.selection_version == ts2_selection

    ts2_grid = state.grid_metadata_version
    state.grid_metadata = GridMetadata(spacing_svg=50.0)
    assert state.grid_metadata_version == ts2_grid
