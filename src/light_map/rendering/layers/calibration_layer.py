import cv2
import numpy as np
from typing import List
from light_map.core.common_types import Layer, LayerMode, ImagePatch, AppConfig
from light_map.state.world_state import WorldState
from light_map.core.display_utils import draw_text_with_background

class CalibrationLayer(Layer):
    """
    Renders calibration-related UI elements based on CalibrationState.
    Matches the CalibrationState fields in common_types.py.
    """

    def __init__(self, state: WorldState, config: AppConfig):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.BLOCKING)
        self.config = config
        self.width = config.width
        self.height = config.height

        # UI Colors (BGR)
        self.target_idle_color = (255, 255, 255)
        self.target_valid_color = (128, 255, 255)
        self.success_color = (0, 150, 0)
        self.instr_text_color = (255, 255, 255)

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(self.state.calibration_version, self.state.system_time_version)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []

        cal = self.state.calibration
        if not cal:
            return []

        # Start with solid background (BGR -> BGRA)
        # SCENE_BG_COLOR = (204, 204, 204)
        bg_color = (204, 204, 204, 255)
        canvas = np.full((self.height, self.width, 4), bg_color, dtype=np.uint8)

        # 1. Pattern Image (Full screen if present)
        if cal.pattern_image is not None:
            img = cal.pattern_image
            if len(img.shape) == 2:
                img_bgra = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
            elif img.shape[2] == 3:
                img_bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            else:
                img_bgra = img.copy()

            if img_bgra.shape[0] == self.height and img_bgra.shape[1] == self.width:
                canvas = img_bgra
            else:
                canvas = cv2.resize(img_bgra, (self.width, self.height))

        # 2. Targets (Extrinsics)
        ppi = self.config.projector_ppi if self.config.projector_ppi > 0 else 96.0

        if cal.target_info and cal.target_status:
            for idx, info in enumerate(cal.target_info):
                if idx >= len(cal.target_status):
                    break
                status = cal.target_status[idx]

                # Positions must be provided in target_info for the layer to render them
                tx = info.get("x")
                ty = info.get("y")
                if tx is None or ty is None:
                    continue

                token_size = info.get("size", 1)
                rect_size = int(token_size * ppi)
                half_size = rect_size // 2

                color = self.target_idle_color
                thickness = 2
                label = "Target"

                if status == "VALID":
                    color = self.target_valid_color
                    thickness = -1  # Filled
                    label = info.get("name", "Locked")

                    height = info.get("height", 0.0)
                    draw_text_with_background(
                        canvas,
                        f"{label}: {height}mm",
                        (int(tx - half_size), int(ty - half_size - 40)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        self.success_color,
                        1,
                    )
                elif status == "UNKNOWN":
                    color = (150, 150, 150)
                    aid = info.get("aid", "???")
                    label = f"Unknown ID {aid}"
                    thickness = 1

                bgra_color = (color[0], color[1], color[2], 255)
                cv2.rectangle(
                    canvas,
                    (int(tx - half_size), int(ty - half_size)),
                    (int(tx + half_size), int(ty + half_size)),
                    bgra_color,
                    thickness,
                )

                draw_text_with_background(
                    canvas,
                    label,
                    (int(tx - half_size), int(ty + half_size) + 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color if thickness > 0 else self.success_color,
                    1 if thickness > 0 else 2,
                )

                # Animation
                if idx in cal.animation_start_times:
                    start_time = cal.animation_start_times[idx]
                    elapsed = current_time - start_time
                    if 0 < elapsed < 0.5:
                        growth = int(20 * (1.0 - elapsed / 0.5))
                        cv2.rectangle(
                            canvas,
                            (int(tx - half_size - growth), int(ty - half_size - growth)),
                            (int(tx + half_size + growth), int(ty + half_size + growth)),
                            (0, 255, 0, 255),
                            2,
                        )

        # 3. Reprojection residuals
        if cal.reprojection_error > 0:
            rms = cal.reprojection_error
            status_color = (
                (0, 255, 0) if rms < 2.0 else (0, 255, 255) if rms < 5.0 else (0, 0, 255)
            )
            status_text = "GOOD" if rms < 2.0 else "FAIR" if rms < 5.0 else "POOR"
            draw_text_with_background(
                canvas,
                f"Error: {rms:.2f} px ({status_text})",
                (self.width // 2 - 130, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                status_color,
                2,
                bg_color=(50, 50, 50),
            )

        # 4. Instructions and Stage
        if cal.stage:
            stage_text = f"STAGE: {cal.stage.upper()}"
            if cal.total_required > 0:
                stage_text += f" ({cal.captured_count}/{cal.total_required})"
            
            draw_text_with_background(
                canvas,
                stage_text,
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),  # Yellow
                2,
                bg_color=(40, 40, 40)
            )

        if cal.instruction_text:
            # Use instruction_pos if provided, otherwise default below stage
            pos = cal.instruction_pos
            if pos == (50, 50) and cal.stage:
                pos = (50, 90)

            draw_text_with_background(
                canvas,
                cal.instruction_text,
                pos,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                self.instr_text_color,
                2,
            )

        # Only return if visible pixels exist
        if not np.any(canvas[:, :, 3]):
            return []

        return [ImagePatch(x=0, y=0, width=self.width, height=self.height, data=canvas)]
