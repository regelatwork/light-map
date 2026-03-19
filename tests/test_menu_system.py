import pytest
from light_map.menu_system import MenuSystem, MenuSystemState
from light_map.common_types import MenuItem, MenuActions, GestureType
from light_map.menu_config import (
    LOCK_DELAY,
    SUMMON_TIME,
    PRIMING_TIME,
    SELECT_GESTURE,
    SUMMON_GESTURE,
)


# --- Mock Time Provider ---
class MockTime:
    def __init__(self):
        self._current = 1000.0

    def __call__(self):
        return self._current

    def advance(self, seconds):
        self._current += seconds


@pytest.fixture
def mock_time():
    return MockTime()


@pytest.fixture
def root_menu():
    return MenuItem(
        title="Root",
        children=[
            MenuItem("Item 1", action_id="ACTION_1"),
            MenuItem("Item 2", action_id="ACTION_2"),
            MenuItem(
                "Submenu", children=[MenuItem("SubItem 1", action_id="SUB_ACTION_1")]
            ),
        ],
    )


@pytest.fixture
def menu_system(root_menu, mock_time):
    # 1000x1000 screen
    return MenuSystem(1000, 1000, root_menu, time_provider=mock_time)


def test_initial_state(menu_system):
    assert menu_system.state == MenuSystemState.HIDDEN

    state = menu_system.update(500, 500, GestureType.OPEN_PALM)
    assert not state.is_visible
    assert state.summon_progress == 0.0


def test_summoning_sequence(menu_system, mock_time):
    # 1. Start Summoning
    state = menu_system.update(500, 500, SUMMON_GESTURE)
    assert state.summon_progress == 0.0
    assert menu_system.summon_start_time == 1000.0

    # 2. Advance half way
    mock_time.advance(SUMMON_TIME * 0.5)
    state = menu_system.update(500, 500, SUMMON_GESTURE)
    assert 0.4 < state.summon_progress < 0.6

    # 3. Complete Summoning
    mock_time.advance(SUMMON_TIME * 0.6)  # Total 1.1x
    state = menu_system.update(500, 500, SUMMON_GESTURE)
    assert menu_system.state == MenuSystemState.WAITING_FOR_NEUTRAL
    assert state.is_visible  # Waiting for neutral is visible? Yes.

    # 4. Release to Neutral to Activate
    state = menu_system.update(500, 500, GestureType.OPEN_PALM)
    assert menu_system.state == MenuSystemState.ACTIVE
    assert state.active_items[0].title == "Item 1"


def test_failed_summon_reset(menu_system, mock_time):
    # Start
    menu_system.update(500, 500, SUMMON_GESTURE)
    mock_time.advance(SUMMON_TIME * 0.5)
    menu_system.update(500, 500, SUMMON_GESTURE)

    # Interrupt
    state = menu_system.update(500, 500, GestureType.OPEN_PALM)
    assert state.summon_progress == 0.0
    assert menu_system.state == MenuSystemState.HIDDEN
    assert menu_system.summon_start_time == 0


def test_navigation_and_hover(menu_system, mock_time):
    # Force Active
    menu_system.state = MenuSystemState.ACTIVE

    # Layout logic:
    # Height 1000. 3 items.
    # Box=80, Gap=20. Total = 3*80 + 2*20 = 240 + 40 = 280.
    # Start Y = (1000 - 280) / 2 = 360.
    # Item 1: 360 -> 440
    # Gap: 440 -> 460
    # Item 2: 460 -> 540

    # Hover Item 1
    state = menu_system.update(500, 400, GestureType.POINTING)  # Y=400 is inside Item 1
    assert state.hovered_item_index == 0
    assert state.active_items[0].title == "Item 1"

    # Hover Item 2
    state = menu_system.update(500, 500, GestureType.POINTING)  # Y=500 is inside Item 2
    assert state.hovered_item_index == 1
    assert state.active_items[1].title == "Item 2"

    # Hover Gap (Should NOT clear hover - sticky logic)
    state = menu_system.update(500, 450, GestureType.POINTING)  # Y=450 is gap
    assert state.hovered_item_index == 1  # Still Item 2


def test_pinning_logic(menu_system, mock_time):
    menu_system.state = MenuSystemState.ACTIVE

    # 1. Fill history with movement
    # t=1000: (500, 500)
    menu_system.update(500, 500, GestureType.POINTING)

    # Advance time to t=1000 + LOCK_DELAY
    # We want the cursor to pin to t=1000 (500, 500)
    # Current pos will be (800, 800) - jittery hand
    mock_time.advance(LOCK_DELAY)

    # Trigger Selection
    state = menu_system.update(800, 800, SELECT_GESTURE)

    assert state.cursor_pos == (500, 500)  # Should be pinned to old pos
    assert menu_system.is_pinning
    assert state.prime_progress == 0.0  # Just started


def test_selection_trigger(menu_system, mock_time):
    menu_system.state = MenuSystemState.ACTIVE

    # Position over Item 1 (360-440)
    menu_system.update(500, 400, GestureType.POINTING)

    # Start Selection
    mock_time.advance(0.1)
    state = menu_system.update(500, 400, SELECT_GESTURE)
    assert menu_system.is_pinning

    # Hold for Priming Time
    mock_time.advance(PRIMING_TIME + 0.01)
    state = menu_system.update(500, 400, SELECT_GESTURE)  # Trigger frame
    assert state.just_triggered_action == "ACTION_1"
    assert not menu_system.is_pinning  # Should reset
    assert menu_system.state == MenuSystemState.HIDDEN  # Default close on trigger


def test_submenu_navigation(menu_system, mock_time):
    menu_system.state = MenuSystemState.ACTIVE

    # Item 3 is Submenu (Index 2)
    # Y range?
    # Item 1: 360-440
    # Item 2: 460-540
    # Item 3: 560-640

    # 1. Select Submenu
    menu_system.update(500, 600, GestureType.OPEN_PALM)  # Hover
    mock_time.advance(LOCK_DELAY + 0.1)  # History buffer
    menu_system.update(500, 600, SELECT_GESTURE)  # Start pin
    mock_time.advance(PRIMING_TIME + 0.01)
    state = menu_system.update(500, 600, SELECT_GESTURE)  # Trigger

    # Should not close, but swap content
    assert menu_system.state == MenuSystemState.ACTIVE
    assert menu_system.current_node.title == "Submenu"

    # 2. Check Back Button Injection
    # Submenu has "SubItem 1".
    # But list should be ["< Back", "SubItem 1"]
    assert len(state.active_items) == 2
    assert state.active_items[0].title == "< Back"
    assert state.active_items[0].action_id == MenuActions.NAV_BACK

    # 3. Trigger Back
    # Hover Back (Item 0)
    # Recalculate layout for 2 items:
    # Total H = 2*80 + 20 = 180. Start Y = (1000-180)/2 = 410.
    # Back: 410-490.

    menu_system.is_pinning = False  # Force reset manually just in case
    menu_system.history.clear()  # Clear stale history from previous steps (test artifact)
    menu_system.update(500, 450, GestureType.OPEN_PALM)  # Hover Back
    mock_time.advance(0.1)
    menu_system.update(500, 450, SELECT_GESTURE)  # Start
    mock_time.advance(PRIMING_TIME + 0.01)
    state = menu_system.update(500, 450, SELECT_GESTURE)  # Trigger Back

    assert menu_system.current_node.title == "Root"
    assert len(state.active_items) == 3  # Back to root items


def test_overflow_layout(menu_system, mock_time):
    # Add many items to root
    many = [MenuItem(f"I{i}") for i in range(10)]
    menu_system.root.children = many
    menu_system.current_node = menu_system.root

    state = menu_system.update(500, 500, GestureType.OPEN_PALM)  # Layout calc

    # MAX_VISIBLE_ITEMS is 8 (from config)
    # Page size = 8 - 2 = 6.
    # Page 0 should show Items 0-5 + "Next Page >" = 7 items.
    assert len(state.active_items) == 7
    assert state.active_items[-1].title == "Next Page >"


def test_trigger_index(menu_system, mock_time):
    # 1. Hidden menu should NOT trigger index (as per user preference)
    menu_system.trigger_index(0)
    state = menu_system.update(500, 500, GestureType.NONE)
    assert state.just_triggered_action is None
    assert menu_system.state == MenuSystemState.HIDDEN

    # 2. Force Active
    menu_system.state = MenuSystemState.ACTIVE

    # Trigger first item (Item 1 with ACTION_1)
    menu_system.trigger_index(0)
    state = menu_system.update(500, 500, GestureType.NONE)

    assert state.just_triggered_action == "ACTION_1"
    assert state.feedback_item_index is None  # Cleared by _reset_to_hidden
    assert menu_system.state == MenuSystemState.HIDDEN  # Closed on trigger


def test_trigger_index_submenu(menu_system, mock_time):
    menu_system.state = MenuSystemState.ACTIVE

    # Trigger Submenu (Index 2)
    menu_system.trigger_index(2)
    state = menu_system.update(500, 500, GestureType.NONE)

    assert menu_system.state == MenuSystemState.ACTIVE
    assert menu_system.current_node.title == "Submenu"
    assert state.feedback_item_index == 2
