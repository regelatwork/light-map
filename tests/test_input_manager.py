import pytest
from light_map.input_manager import InputManager
from light_map.common_types import GestureType


class MockTimeProvider:
    def __init__(self):
        self.time = 0.0

    def __call__(self):
        return self.time


@pytest.fixture
def time_provider():
    return MockTimeProvider()


@pytest.fixture
def input_manager(time_provider):
    return InputManager(flicker_timeout=0.5, time_provider=time_provider)


def test_initial_state(input_manager):
    assert not input_manager.is_hand_present()
    assert input_manager.get_gesture() == GestureType.NONE


def test_update_valid_input(input_manager, time_provider):
    time_provider.time = 1.0
    input_manager.update(100, 200, GestureType.OPEN_PALM, is_present=True)

    assert input_manager.is_hand_present()
    assert input_manager.get_x() == 100
    assert input_manager.get_y() == 200
    assert input_manager.get_gesture() == GestureType.OPEN_PALM


def test_flicker_recovery(input_manager, time_provider):
    # 1. Establish presence
    time_provider.time = 1.0
    input_manager.update(100, 200, GestureType.VICTORY, is_present=True)
    assert input_manager.is_hand_present()

    # 2. Lose presence briefly (0.2s later)
    time_provider.time = 1.2
    input_manager.update(0, 0, GestureType.NONE, is_present=False)

    # Should still be "present" (recovering)
    # And should retain OLD values
    assert input_manager.is_hand_present()
    assert input_manager.get_x() == 100
    assert input_manager.get_y() == 200
    assert input_manager.get_gesture() == GestureType.VICTORY


def test_flicker_timeout(input_manager, time_provider):
    # 1. Establish presence
    time_provider.time = 1.0
    input_manager.update(100, 200, GestureType.VICTORY, is_present=True)

    # 2. Lose presence for long time (0.6s later > 0.5s timeout)
    time_provider.time = 1.6
    input_manager.update(0, 0, GestureType.NONE, is_present=False)

    # Should be gone
    assert not input_manager.is_hand_present()
    assert input_manager.get_gesture() == GestureType.NONE


def test_keyboard_debug_and_quit(input_manager):
    from light_map.common_types import Action

    # Check 'd' and 'D'
    for k in ["d", "D"]:
        input_manager.update_keyboard(ord(k))
        actions = input_manager.get_actions()
        assert Action.TOGGLE_DEBUG in actions

    # Check 'q' and 'Q'
    for k in ["q", "Q"]:
        input_manager.update_keyboard(ord(k))
        actions = input_manager.get_actions()
        assert Action.QUIT in actions
