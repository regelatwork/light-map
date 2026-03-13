from unittest.mock import MagicMock
import time
from light_map.core.main_loop import MainLoopController
from light_map.core.world_state import WorldState
from light_map.common_types import DetectionResult, ResultType, Token
from light_map.overlay_layer import TokenLayer
from light_map.core.app_context import AppContext


def test_tokens_persist_when_none_detected():
    """
    Reproduction test for tokens persisting in WorldState even when
    the detector returns an empty list (physical tokens removed).
    """
    state = WorldState()
    manager = MagicMock()
    manager.results_queue = MagicMock()
    input_mgr = MagicMock()

    controller = MainLoopController(state, manager, input_mgr)

    # 1. Simulate finding one token
    token1 = Token(id=1, world_x=100, world_y=100)
    res1 = DetectionResult(
        timestamp=time.perf_counter_ns(),
        type=ResultType.ARUCO,
        data={"tokens": [token1], "raw_tokens": [token1]},
    )

    # Mock queue to return res1 then be empty
    manager.results_queue.empty.side_effect = [False, True]
    manager.results_queue.get_nowait.return_value = res1

    controller.tick()

    assert len(state.tokens) == 1
    assert state.tokens[0].id == 1

    # 2. Simulate finding NO tokens (physical removal)
    res_empty = DetectionResult(
        timestamp=time.perf_counter_ns(),
        type=ResultType.ARUCO,
        data={"tokens": [], "raw_tokens": []},
    )

    # Mock queue to return res_empty then be empty
    manager.results_queue.empty.side_effect = [False, True]
    manager.results_queue.get_nowait.return_value = res_empty

    controller.tick()

    # BUG: This assertion is expected to FAIL with current implementation
    # because MainLoopController._drain_queues applies any ARUCO result,
    # but let's check the aruco_mapper branch in tick() too.

    # Wait, let's look at _drain_queues again in main_loop.py:
    # def _drain_queues(self, current_time: float) -> set[ResultType]:
    #     ...
    #     self.state.apply(res, current_time=current_time)

    # And WorldState.apply:
    # if "tokens" in result.data:
    #     new_tokens = result.data["tokens"]
    #     if not self._tokens_equal(self.tokens, new_tokens):
    #         self.tokens = new_tokens

    # Actually, _drain_queues SHOULD work if it receives an ARUCO result with empty tokens.
    # But where does the ARUCO result come from?
    # In tick():
    # if self.state.raw_aruco["ids"]:
    #     if self.aruco_mapper:
    #         mapped_result = self.aruco_mapper(self.state.raw_aruco)
    #         ...
    #         if new_tokens or new_raw_tokens:
    #             ...
    #             self.state.apply(res, current_time=current_mono)

    # This branch in tick() ONLY applies if new_tokens is NOT empty.
    # But this branch only runs if self.state.raw_aruco["ids"] is truthy.
    # If raw_aruco is empty, this branch is skipped.

    # Let's test the queue-based path first.
    assert len(state.tokens) == 0, (
        "Tokens should be cleared when empty result is received"
    )


def test_tokens_persist_via_aruco_mapper_path():
    """
    Reproduction test for tokens persisting when using the aruco_mapper path in tick().
    """
    state = WorldState()
    manager = MagicMock()
    manager.results_queue.empty.return_value = True
    input_mgr = MagicMock()

    # Mock aruco_mapper
    def mock_mapper(raw_data):
        return {"tokens": [], "raw_tokens": []}

    controller = MainLoopController(state, manager, input_mgr, aruco_mapper=mock_mapper)

    # 1. Set initial tokens
    token1 = Token(id=1, world_x=100, world_y=100)
    state.tokens = [token1]
    state.tokens_timestamp = 1

    # 2. Set raw_aruco to something so the mapper is called
    state.raw_aruco = {"ids": [1], "corners": [None]}

    controller.tick()

    # BUG: state.tokens will still have token1 because 'if new_tokens or new_raw_tokens' is false
    assert len(state.tokens) == 0, "Tokens should be cleared by mapper even if empty"


def test_token_layer_dirty_when_occluded():
    """
    Verify that TokenLayer is dirty every frame if a token is occluded.
    """
    state = WorldState()
    # Use a list to hold time so it can be mutated inside closure
    current_time = [100.0]

    def mock_time():
        return current_time[0]

    ctx = MagicMock(spec=AppContext)
    ctx.show_tokens = True
    ctx.map_config_manager = MagicMock()
    ctx.map_config_manager.get_ppi.return_value = 100.0
    ctx.map_system = MagicMock()
    ctx.map_system.ghost_tokens = []

    layer = TokenLayer(state, ctx, time_provider=mock_time)

    # 1. Non-occluded token
    token1 = Token(id=1, world_x=100, world_y=100, is_occluded=False)
    state.tokens = [token1]
    state.tokens_timestamp = 1

    # First check: should be dirty because timestamp changed
    assert layer.is_dirty
    layer.render()  # Clears dirty flag

    # Second check (same time): should NOT be dirty
    assert not layer.is_dirty

    # 2. Occluded token
    token1.is_occluded = True
    # Reset timestamp so it only depends on occlusion
    layer._last_state_timestamp = state.tokens_timestamp

    # Even without timestamp change, it should be dirty because of occlusion
    assert layer.is_dirty

    layer.render()
    # Should STILL be dirty for next frame to continue pulse
    assert layer.is_dirty


def test_token_layer_pulse_dirty():
    """
    Verify that TokenLayer is dirty every 500ms even if no tokens are occluded.
    """
    state = WorldState()
    current_time = [100.0]

    def mock_time():
        return current_time[0]

    ctx = MagicMock(spec=AppContext)
    ctx.show_tokens = True
    ctx.map_config_manager = MagicMock()
    ctx.map_config_manager.get_ppi.return_value = 100.0
    ctx.map_system = MagicMock()
    ctx.map_system.ghost_tokens = []

    layer = TokenLayer(state, ctx, time_provider=mock_time)

    token1 = Token(id=1, world_x=100, world_y=100, is_occluded=False)
    state.tokens = [token1]
    state.tokens_timestamp = 1

    layer.render()
    assert not layer.is_dirty

    # Advance time by 0.1s: should NOT be dirty
    current_time[0] += 0.1
    assert not layer.is_dirty

    # Advance time by 0.6s total: should BE dirty
    current_time[0] += 0.5
    assert layer.is_dirty
