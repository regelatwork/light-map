import cv2
import numpy as np

from light_map.core.common_types import AppConfig, ImagePatch, Layer, LayerMode
from light_map.core.display_utils import draw_text_with_background
from light_map.state.world_state import WorldState


class InstructionLayer(Layer):
    """
    Renders user-facing HUD instructions and stage indicators.
    Separates instructional text rendering from calibration patterns and target geometries.
    """

    def __init__(
        self,
        state: WorldState | None = None,
        config: AppConfig | None = None,
        instructions: str = "",
        stage: str = "",
        pos: tuple[int, int] = (50, 50),
    ):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.config = config
        self.width = config.width if config else 1920
        self.height = config.height if config else 1080
        self.instructions = instructions
        self.stage = stage
        self.pos = pos
        self.text_color = (255, 255, 255)
        self.stage_color = (0, 255, 255)  # Yellow
        self.bg_color = (40, 40, 40)
        self.alpha = 0.85

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(self.state.calibration_version, self.state.scene_version)

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        if self.width <= 0 or self.height <= 0:
            return []

        stage_text = ""
        instruction_text = self.instructions
        pos = self.pos

        if self.state and self.state.calibration:
            cal = self.state.calibration
            if cal.stage:
                stage_text = f"STAGE: {cal.stage.upper()}"
                if cal.total_required > 0:
                    stage_text += f" ({cal.captured_count}/{cal.total_required})"
            if cal.instruction_text:
                instruction_text = cal.instruction_text
            if cal.instruction_pos != (50, 50):
                pos = cal.instruction_pos
        elif self.stage:
            stage_text = f"STAGE: {self.stage.upper()}"

        if not stage_text and not instruction_text:
            return []

        # Render onto a transparent canvas (NORMAL blend mode)
        canvas = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        if stage_text:
            draw_text_with_background(
                canvas,
                stage_text,
                (pos[0], pos[1]),
                font=cv2.FONT_HERSHEY_SIMPLEX,
                scale=0.7,
                color=self.stage_color,
                thickness=2,
                bg_color=self.bg_color,
                alpha=self.alpha,
            )

        if instruction_text:
            instr_pos = (pos[0], pos[1] + 40) if stage_text else pos
            draw_text_with_background(
                canvas,
                instruction_text,
                instr_pos,
                font=cv2.FONT_HERSHEY_SIMPLEX,
                scale=0.8,
                color=self.text_color,
                thickness=2,
                bg_color=self.bg_color,
                alpha=self.alpha,
            )

        if not np.any(canvas[:, :, 3]):
            return []

        return [ImagePatch(x=0, y=0, width=self.width, height=self.height, data=canvas)]
