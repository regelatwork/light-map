import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import AppMode, Token
from light_map.menu_config import ROOT_MENU


# Reuse Mock classes from test_viewing_mode
class MockHandLandmark:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z


class MockResults:
    def __init__(
        self,
        hands_landmarks=None,
        labels=None,
    ):
        if hands_landmarks:
            self.multi_hand_landmarks = [
                MagicMock(landmark=lm) for lm in hands_landmarks
            ]
            self.multi_handedness = []
            for label in labels or ["Right"] * len(hands_landmarks):
                classification = MagicMock()
                classification.label = label
                self.multi_handedness.append(MagicMock(classification=[classification]))
        else:
            self.multi_hand_landmarks = None
            self.multi_handedness = None


@pytest.fixture
def app_config():
    matrix = np.eye(3, dtype=np.float32)
    return AppConfig(
        width=100, height=100, projector_matrix=matrix, root_menu=ROOT_MENU
    )


def test_token_count_display_no_tokens(app_config):
    app = InteractiveApp(app_config)
    app.mode = AppMode.VIEWING
    app.show_tokens = True
    app.ghost_tokens = []

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()  # No hands

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Check if "Tokens: 0" was drawn
        # cv2.putText(img, text, org, font, fontScale, color, thickness)
        found = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "Tokens: 0":
                found = True
                break
        assert found, "Token count 'Tokens: 0' not found in cv2.putText calls"


def test_token_count_display_with_tokens(app_config):
    app = InteractiveApp(app_config)
    app.mode = AppMode.VIEWING
    app.show_tokens = True
    app.ghost_tokens = [Token(1, 10, 10), Token(2, 20, 20)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()  # No hands

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Check if "Tokens: 2" was drawn
        found = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "Tokens: 2":
                found = True
                break
        assert found, "Token count 'Tokens: 2' not found in cv2.putText calls"


def test_token_count_hidden_when_toggled_off(app_config):
    app = InteractiveApp(app_config)
    app.mode = AppMode.VIEWING
    app.show_tokens = False
    app.ghost_tokens = [Token(1, 10, 10)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Check that NO "Tokens: ..." was drawn
        for call in mock_putText.call_args_list:
            args, _ = call
            if isinstance(args[1], str) and args[1].startswith("Tokens:"):
                pytest.fail(f"Found token count '{args[1]}' when show_tokens is False")
