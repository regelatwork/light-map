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

    # 1. Set initial tokens via apply() to ensure manager state is synced
    token1 = Token(id=1, world_x=100, world_y=100)
    res_init = DetectionResult(
        timestamp=0,
        type=ResultType.ARUCO,
        data={"tokens": [token1], "raw_tokens": [token1]},
    )
    res_init.metadata["source"] = "physical"
    state.apply(res_init)

    assert len(state.tokens) == 1

    # 2. Set raw_aruco to something so the mapper is called
    state.raw_aruco = {"ids": [1], "corners": [None]}
    state.raw_aruco_timestamp = 1  # Ensure it differs from _last_raw_aruco_ts

    controller.tick()

    # BUG: state.tokens will still have token1 because 'if new_tokens or new_raw_tokens' is false
    assert len(state.tokens) == 0, "Tokens should be cleared by mapper even if empty"


def test_token_layer_stale_when_occluded():
    """
    Verify that TokenLayer version increments every frame if a token is occluded.
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

    # First check: version should be based on timestamp
    v1 = layer.get_current_version()
    assert v1 >= state.tokens_timestamp

    patches, rv1 = layer.render()
    assert rv1 == v1

    # Second check (same time): version should be same, render shouldn't happen
    # (actually get_current_version just returns the number)
    v2 = layer.get_current_version()
    assert v2 == v1

    # 2. Occluded token
    token1.is_occluded = True

    # Occlusion makes it dynamic
    v3 = layer.get_current_version()
    assert layer._is_dynamic is True

    # Render should still return version
    patches, rv3 = layer.render()
    assert rv3 == v3


def test_token_layer_pulse_version():
    """
    Verify that TokenLayer version increments every 500ms even if no tokens are occluded.
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

    patches, v1 = layer.render()

    # Advance time by 0.1s: version might still be same (time_version based on now*2)
    current_time[0] += 0.1
    v2 = layer.get_current_version()
    assert v2 == v1

    # Advance time by 0.6s total: time_version should increment
    current_time[0] += 0.5
    v3 = layer.get_current_version()
    assert v3 > v1
