import pytest
from unittest.mock import MagicMock
from light_map.scenes.map_scene import ViewingScene
from light_map.core.app_context import AppContext
from light_map.core.scene import HandInput
from light_map.gestures import GestureType
from light_map.common_types import TimerKey
import light_map.menu_config as config_vars


@pytest.fixture
def viewing_scene_context():
    context = MagicMock(spec=AppContext)
    context.events = MagicMock()
    context.notifications = MagicMock()
    context.app_config = MagicMock()
    context.app_config.projector_ppi = 96.0
    context.show_tokens = True
    context.inspected_token_id = None
    return context


def test_viewing_scene_robust_summon_step_1(viewing_scene_context):
    scene = ViewingScene(viewing_scene_context)

    # Step 1: VICTORY
    inputs = [HandInput(GestureType.VICTORY, (100, 100), (0.0, 0.0), None)]

    # Not ready yet
    viewing_scene_context.events.has_event.side_effect = lambda k: False

    scene.update(inputs, [], 0.0)

    # Verify Step 1 timer was scheduled
    viewing_scene_context.events.schedule.assert_any_call(
        config_vars.SUMMON_STEP_1_TIME,
        scene._on_summon_step1_complete,
        key=TimerKey.SUMMON_MENU_STEP_1,
    )


def test_viewing_scene_robust_summon_step_2_ready(viewing_scene_context):
    scene = ViewingScene(viewing_scene_context)

    # Simulate Step 1 complete (TimerKey.SUMMON_MENU is present)
    viewing_scene_context.events.has_event.side_effect = lambda k: (
        k == TimerKey.SUMMON_MENU
    )

    # Step 2: SHAKA
    inputs = [HandInput(GestureType.SHAKA, (100, 100), (0.0, 0.0), None)]

    # We need to make sure has_event returns True for SUMMON_MENU but False for SUMMON_MENU_STEP_2 initially
    def mock_has_event(k):
        if k == TimerKey.SUMMON_MENU:
            return True
        return False

    viewing_scene_context.events.has_event.side_effect = mock_has_event

    scene.update(inputs, [], 0.0)

    # Verify Step 2 timer was scheduled
    # The callback for Action.TRIGGER_MENU is a lambda, so we can't easily check it
    # But we can check the key.
    found_step2 = False
    for call in viewing_scene_context.events.schedule.call_args_list:
        args, kwargs = call
        if kwargs.get("key") == TimerKey.SUMMON_MENU_STEP_2:
            assert args[0] == config_vars.SUMMON_STEP_2_TIME
            found_step2 = True
    assert found_step2


def test_on_summon_step1_complete(viewing_scene_context):
    scene = ViewingScene(viewing_scene_context)
    scene._on_summon_step1_complete()

    # Verify notification
    viewing_scene_context.notifications.add_notification.assert_called_once()

    # Verify SUMMON_MENU (ready marker) scheduled
    viewing_scene_context.events.schedule.assert_called_once()
    args, kwargs = viewing_scene_context.events.schedule.call_args
    assert kwargs["key"] == TimerKey.SUMMON_MENU
    assert args[0] == 5.0
