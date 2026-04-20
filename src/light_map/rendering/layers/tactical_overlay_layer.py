from typing import List, TYPE_CHECKING
import cv2
import numpy as np
from light_map.core.common_types import ImagePatch, Layer, LayerMode
from light_map.core.display_utils import draw_text_with_background

if TYPE_CHECKING:
    from light_map.state.world_state import WorldState
    from light_map.map.map_system import MapSystem
    from light_map.visibility.visibility_engine import VisibilityEngine


class TacticalOverlayLayer(Layer):
    """
    Renders floating tactical labels (AC/Reflex bonuses) below tokens.
    Active during Exclusive Vision inspection.
    """

    def __init__(
        self,
        state: "WorldState",
        map_system: "MapSystem",
        visibility_engine: "VisibilityEngine",
    ):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.map_system = map_system
        self.visibility_engine = visibility_engine

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        # Re-render if tokens or viewport change
        return max(
            self.state.tokens_version,
            self.state.viewport_version,
            self.state.inspected_token_version,
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if (
            self.state is None
            or self.state.inspected_token_id is None
            or self.state.inspected_token_mask is None
        ):
            return []

        patches = []
        mask = self.state.inspected_token_mask
        mask_h, mask_w = mask.shape[:2]
        
        # We need the scale to check the mask
        # visibility_engine is already in self
        scale = self.visibility_engine.svg_to_mask_scale

        for token in self.state.tokens:
            if token.id == self.state.inspected_token_id:
                continue
                
            # Calculate screen coordinates
            sx, sy = self.map_system.world_to_screen(token.world_x, token.world_y)
            
            # Check visibility in mask
            mx = int(token.world_x * scale)
            my = int(token.world_y * scale)
            
            is_visible = False
            if 0 <= mx < mask_w and 0 <= my < mask_h:
                if mask[my, mx] > 0:
                    is_visible = True
            
            if not is_visible:
                continue

            # Determine label text and color
            if token.cover_bonus == -1:
                label = "TOTAL COVER"
                color = (0, 0, 255) # Red
            elif token.cover_bonus > 0 or token.reflex_bonus > 0:
                label = f"+{token.cover_bonus} AC / +{token.reflex_bonus} Reflex"
                color = (0, 255, 0) # Green
            else:
                label = "CLEAR LOS"
                color = (255, 255, 0) # Cyan (BGR)

            # Render text using unified utility
            lw, lh = 250, 40
            text_img = np.zeros((lh, lw, 4), dtype=np.uint8)
            
            draw_text_with_background(
                text_img,
                label,
                (10, lh // 2 + 5),
                font=cv2.FONT_HERSHEY_SIMPLEX,
                scale=0.4,
                color=(*color, 255),
                thickness=1,
                bg_color=(0, 0, 0),
                alpha=0.8,
            )

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            patch_w = tw + 20
            
            patches.append(
                ImagePatch(
                    x=int(sx - patch_w // 2),
                    y=int(sy + 20),
                    width=patch_w,
                    height=lh,
                    data=text_img[:lh, :patch_w].copy(),
                )
            )
            
        return patches
