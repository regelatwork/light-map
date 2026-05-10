import cv2
import numpy as np
import time
from light_map.core.common_types import ImagePatch, Layer
from light_map.state.world_state import WorldState
from light_map.core.app_context import AppContext

class PingLayer(Layer):
    """
    Renders pulsating rings around tokens to highlight them (pings).
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False)
        self.context = context
        self.duration = 2.0  # Seconds
        self.max_radius_px = 60
        self.color_bgra = (255, 255, 0, 255)  # Cyan/Yellow-ish (B, G, R, A)

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        # PingLayer depends on active_pings and system_time for animation
        return max(self.state.active_pings_version, self.state.system_time_version)

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        if self.state is None or not self.state.active_pings:
            return []

        patches = []
        
        # We need token positions to render pings
        token_map = {t.id: t for t in self.state.tokens}
        
        for token_id, start_time in list(self.state.active_pings.items()):
            elapsed = current_time - start_time
            if elapsed < 0 or elapsed > self.duration:
                continue
            
            token = token_map.get(token_id)
            if not token:
                continue

            # Project world coordinates to screen pixels
            screen_pos = self.context.projector_model.project_to_screen(
                token.x, token.y, token.z
            )
            if screen_pos is None:
                continue
            
            cx, cy = int(screen_pos[0]), int(screen_pos[1])

            # Calculate pulse effects
            # Pulse 1: 0 -> 1 -> 0 -> 1 ... (faster)
            # Or just a single expanding ring that fades
            progress = elapsed / self.duration
            
            # Draw 2-3 rings with different scales
            for i in range(3):
                ring_progress = (progress + i * 0.3) % 1.0
                radius = int(ring_progress * self.max_radius_px)
                alpha = int((1.0 - ring_progress) * 255)
                
                if radius <= 0:
                    continue

                w, h = radius * 2 + 4, radius * 2 + 4
                buffer = np.zeros((h, w, 4), dtype=np.uint8)
                center = (w // 2, h // 2)
                
                # Draw the ring
                color = (self.color_bgra[0], self.color_bgra[1], self.color_bgra[2], alpha)
                cv2.circle(buffer, center, radius, color, 2)
                
                patches.append(
                    ImagePatch(
                        x=cx - w // 2,
                        y=cy - h // 2,
                        width=w,
                        height=h,
                        data=buffer
                    )
                )

        return patches
