from light_map.input_manager import InputManager
from light_map.common_types import GestureType, Action


def test_input_manager_semantic_actions():
    manager = InputManager()

    # Test Gesture -> Action
    manager.update(x=100, y=100, gesture=GestureType.VICTORY, is_present=True)
    actions = manager.get_actions()
    assert Action.SELECT in actions

    # Test Keyboard -> Action (Mocked waitKey)
    # We will need to mock cv2.waitKey in the implementation or test
    pass


def test_input_manager_gesture_mapping():
    manager = InputManager()

    # Open Palm -> Back
    manager.update(x=100, y=100, gesture=GestureType.OPEN_PALM, is_present=True)
    assert Action.BACK in manager.get_actions()

    # Pointing -> Move (Hover)
    manager.update(x=100, y=100, gesture=GestureType.POINTING, is_present=True)
    assert Action.MOVE in manager.get_actions()
