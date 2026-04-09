from __future__ import annotations
from typing import TYPE_CHECKING
from light_map.vision.processing.input_processor import DummyResults

if TYPE_CHECKING:
    from light_map.interactive_app import InteractiveApp
    from light_map.state.world_state import WorldState


class InputCoordinator:
    """
    Standardizes vision inputs (MediaPipe landmarks vs Remote Driver inputs)
     and manages their lifecycle/expiration.
    """

    def __init__(self, app: "InteractiveApp"):
        self.app = app
        self.config = app.config
        self.input_processor = app.input_processor
        self.flicker_timeout = 0.5

    def update(self, state: "WorldState", current_time: float):
        """Standardizes vision inputs and manages their lifecycle."""
        # Determine frame shape for normalization
        if state.background is not None:
            self.app.app_context.last_camera_frame = state.background
            frame_shape = state.background.shape
        else:
            frame_shape = (self.config.height, self.config.width, 3)

        # Standardize Input
        # Priority 1: Raw landmarks from physical camera
        if state.hands or state.handedness:
            results = DummyResults(state.hands, state.handedness)
            inputs = self.input_processor.convert_mediapipe_to_inputs(
                results, frame_shape, projector_pose=state.projector_pose
            )
            state.update_inputs(inputs, current_time)
        # Priority 2: Use existing inputs (might be from Remote Driver)
        else:
            inputs = state.inputs
            # Expire inputs if no update received for > flicker_timeout
            if inputs and (
                current_time - state.last_hand_timestamp > self.flicker_timeout
            ):
                state.inputs = []

        # Sync common vision results to AppContext
        self.app.app_context.last_camera_frame = state.background
        self.app.app_context.raw_aruco = state.raw_aruco
        self.app.app_context.raw_tokens = state.raw_tokens

        # Update app inspected token id
        self.app.inspected_token_id = self.app.app_context.inspected_token_id
