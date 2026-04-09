import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp
from light_map.core.common_types import AppConfig, TimerKey
import light_map.menu.menu_config as config_vars


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 100
    config.height = 100
    config.map_search_patterns = []
    config.storage_manager = None
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.enable_hand_masking = False
    config.hand_mask_padding = 0
    config.camera_resolution = (100, 100)
    config.projector_matrix_resolution = (100, 100)
    config.projector_ppi = 96.0
    return config


def test_interactive_app_summon_progress_update(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    t = 0.0
    app = InteractiveApp(mock_config, time_provider=lambda: t)
    ws = app.state

    # Mock current_scene and renderer to avoid failures
    app.current_scene = MagicMock()
    app.current_scene.render.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), 1)
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = []

    # Mock TemporalEventManager to simulate summoning
    app.events.schedule(
        config_vars.SUMMON_STEP_1_TIME, lambda: None, key=TimerKey.SUMMON_MENU_STEP_1
    )

    # 1. Start of Step 1
    t = 0.0
    app.process_state(ws, [])
    assert ws.summon_progress == pytest.approx(0.0)

    # 2. Middle of Step 1
    t = 1.0
    app.process_state(ws, [])
    # Step 1 time is 2.0s. At 1.0s, progress should be 0.5
    assert ws.summon_progress == pytest.approx(0.5)

    # 3. End of Step 1 / Transition
    app.events.cancel(TimerKey.SUMMON_MENU_STEP_1)
    app.events.schedule(
        config_vars.SUMMON_STEP_2_TIME, lambda: None, key=TimerKey.SUMMON_MENU_STEP_2
    )
    t = 1.0  # Current time is 1.0, but we just scheduled Step 2
    app.process_state(ws, [])
    assert ws.summon_progress == pytest.approx(0.0)

    # 4. Middle of Step 2
    t = 2.0  # 1.0s since scheduling Step 2
    app.process_state(ws, [])
    # Step 2 time is 2.0s. At 1.0s after schedule, progress should be 0.5
    assert ws.summon_progress == pytest.approx(0.5)

    # 5. No summoning
    app.events.cancel(TimerKey.SUMMON_MENU_STEP_2)
    app.process_state(ws, [])
    assert ws.summon_progress == 0.0


def test_interactive_app_summon_progress_map_scene(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    t = 0.0
    app = InteractiveApp(mock_config, time_provider=lambda: t)
    ws = app.state

    app.current_scene = MagicMock()
    app.current_scene.__class__.__name__ = "MapScene"
    app.current_scene_name = "MapScene"
    app.current_scene.render.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), 1)
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = []

    # MapScene uses SUMMON_MENU for direct summoning
    app.events.schedule(config_vars.SUMMON_TIME, lambda: None, key=TimerKey.SUMMON_MENU)

    t = 0.5
    app.process_state(ws, [])
    # SUMMON_TIME is 1.0s. At 0.5s, progress should be 0.5
    assert ws.summon_progress == pytest.approx(0.5)
