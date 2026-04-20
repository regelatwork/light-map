import cv2
import numpy as np
from typing import List, TYPE_CHECKING
from light_map.core.common_types import ImagePatch, Layer, LayerMode

if TYPE_CHECKING:
    from light_map.state.world_state import WorldState


class TacticalOverlayLayer(Layer):
    """
    Renders floating tactical labels (AC/Reflex bonuses) below tokens.
    Active during Exclusive Vision inspection.
    """

    def __init__(self, state: "WorldState"):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)

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
        if self.state is None or self.state.inspected_token_id is None:
            return []

        # Create a transparent overlay at full screen resolution
        # Note: In a real implementation, we might want to crop this to token areas
        # but for simplicity we'll use a full-frame patch.
        # However, Layer expected to return patches.
        
        # Actually, let's render labels into a small patch for each token
        patches = []
        
        for token in self.state.tokens:
            # Only render for NPCs if PC is inspecting, or for PCs if NPC is inspecting
            # Actually, the 'inspected' token is the source. We render for everyone ELSE.
            if token.id == self.state.inspected_token_id:
                continue
                
            if token.screen_x is None or token.screen_y is None:
                continue

            # Skip if no bonus and not Total Cover
            if token.cover_bonus == 0 and token.reflex_bonus == 0:
                continue

            # Determine label text
            if token.cover_bonus == -1:
                label = "TOTAL COVER"
                color = (0, 0, 255) # Red
            else:
                label = f"+{token.cover_bonus} AC / +{token.reflex_bonus} Reflex"
                color = (0, 255, 0) # Green

            # Render text to a small buffer
            # We'll use a fixed size for the label patch
            lw, lh = 200, 30
            text_img = np.zeros((lh, lw, 4), dtype=np.uint8)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.4
            thickness = 1
            
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            
            # Draw semi-transparent background box
            cv2.rectangle(text_img, (0, 0), (tw + 10, lh), (0, 0, 0, 180), -1)
            # Draw text
            cv2.putText(
                text_img,
                label,
                (5, th + 5),
                font,
                font_scale,
                (*color, 255),
                thickness,
                cv2.LINE_AA,
            )

            patches.append(
                ImagePatch(
                    data=text_img[:lh, :tw+10],
                    x=int(token.screen_x - tw//2),
                    y=int(token.screen_y + 20), # Offset below token
                )
            )
            
        return patches
