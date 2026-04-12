import time

import numpy as np
import pytest

from light_map.core.common_types import Action, AppConfig, GestureType, TimerKey
from light_map.state.temporal_event_manager import TemporalEventManager
from light_map.input.dwell_tracker import DwellTracker
from light_map.vision.processing.input_processor import DummyResults, InputProcessor


def test_dwell_tracker_basic():
    # 10 pixel radius, 2 second threshold
    events = TemporalEventManager()
    t = 0.0
    events.time_provider = lambda: t
    tracker = DwellTracker(radius_pixels=10, dwell_time_threshold=2.0, events=events)

    # First update
    assert tracker.update((100, 100), 0.5) is False
    assert tracker.accumulated_time == pytest.approx(0.0, abs=1e-5)

    # Stable update
    # We need to simulate time passing for TemporalEventManager
    t = 1.0
    assert tracker.update((102, 102), 1.0) is False
    # rem = 2.0 - (1.0 - 0.0) = 1.0
    assert tracker.accumulated_time == pytest.approx(1.0, abs=1e-5)

    # Reached threshold
    t = 2.1
    events.check()  # Trigger the dwell
    assert tracker.update((101, 99), 1.1) is True
    assert tracker.accumulated_time == pytest.approx(2.0, abs=1e-5)
    assert tracker.is_triggered is True

    # Subsequent stable updates shouldn't re-trigger
    assert tracker.update((100, 100), 0.5) is False


def test_dwell_tracker_with_events():
    events = TemporalEventManager()
    # 10 pixel radius, 2 second threshold
    tracker = DwellTracker(radius_pixels=10, dwell_time_threshold=2.0, events=events)

    # First update: should schedule event
    assert tracker.update((100, 100), 0.5) is False
    assert events.has_event((TimerKey.DWELL, id(tracker)))

    # Stable update: should NOT return true yet, and should NOT reschedule
    # We simulate some time passing but not enough
    assert tracker.update((102, 102), 1.0) is False

    # Now simulate event firing.
    # Instead of real time, let's mock the callback execution or just wait.
    # Actually, let's just wait a bit and check.
    time.sleep(2.1)
    results = events.check()
    assert Action.DWELL_TRIGGER in results

    # Now the NEXT update() should return True
    assert tracker.update((101, 101), 0.1) is True
    # And subsequently False
    assert tracker.update((101, 101), 0.1) is False


def test_input_processor_virtual_pointer_offset(mocker):
    # Mock config
    config = mocker.Mock(spec=AppConfig)
    config.width = 1920
    config.height = 1080
    config.projector_matrix = np.eye(3)
    config.projector_ppi = 100.0  # 100 pixels per inch
    config.pointer_offset_mm = 50.8
    config.distortion_model = None
    config.gm_position = "None"

    processor = InputProcessor(config)

    # Create dummy landmarks for POINTING
    # Index finger PIP at (0.5, 0.5), Tip at (0.5, 0.4) -> pointing UP in cam space
    landmarks = [{"x": 0.0, "y": 0.0}] * 21
    landmarks[6] = {"x": 0.5, "y": 0.5}  # PIP
    landmarks[8] = {"x": 0.5, "y": 0.4}  # TIP

    results = DummyResults([landmarks], [{"label": "Right", "score": 1.0}])

    # Mock detect_gesture to return POINTING
    mocker.patch(
        "light_map.vision.processing.input_processor.detect_gesture",
        return_value=GestureType.POINTING,
    )

    inputs = processor.convert_mediapipe_to_inputs(results, (1080, 1920, 3))

    assert len(inputs) == 1
    inp = inputs[0]

    # Tip at (0.5, 0.4) maps to (960, 432) in 1920x1080
    assert inp.proj_pos == (960, 432)

    # Pointing UP in cam space should roughly be pointing UP in projector space with identity matrix
    # uy should be negative
    assert inp.unit_direction[0] == pytest.approx(0.0, abs=0.01)
    assert inp.unit_direction[1] == pytest.approx(-1.0, abs=0.01)
    # Should be unit vector
    mag = np.sqrt(inp.unit_direction[0] ** 2 + inp.unit_direction[1] ** 2)
    assert pytest.approx(mag) == 1.0

    # cursor_pos = proj_pos + direction * ppi * extension
    # cx = 960 + 0 * 100 * 2 = 960
    # cy = 432 + (-1) * 100 * 2 = 232
    assert inp.cursor_pos == (960, 232)
