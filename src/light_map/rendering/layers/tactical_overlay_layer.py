from typing import List, TYPE_CHECKING
import cv2
import numpy as np
import math
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
        # Re-render if tokens, viewport, or tactical calculations change
        return max(
            self.state.tokens_version,
            self.state.viewport_version,
            self.state.inspected_token_id_version,
            self.state.inspected_token_mask_version,
            self.state.tactical_bonuses_version,
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if (
            self.state is None
            or self.state.inspected_token_id is None
            or self.state.inspected_token_mask is None
        ):
            return []

        patches = []
        
        # 1. Render Visual Wedges (Polygons)
        bonuses = self.state.tactical_bonuses
        if bonuses:
            screen_w = self.map_system.config.width if self.map_system.config else 1920
            screen_h = self.map_system.config.height if self.map_system.config else 1080
            
            # Create a single large patch for all wedges
            wedge_img = np.zeros((screen_h, screen_w, 4), dtype=np.uint8)
            
            # Create stipple mask (2x2 dots in a 4x4 tile for high visibility)
            tile = np.zeros((4, 4), dtype=np.uint8)
            tile[0:2, 0:2] = 255
            tile[2:4, 2:4] = 255
            stipple_mask = np.tile(tile, (screen_h // 4 + 1, screen_w // 4 + 1))[:screen_h, :screen_w]
            
            svg_to_mask_scale = self.visibility_engine.svg_to_mask_scale
            inv_scale = 1.0 / svg_to_mask_scale
            
            drawn_any_wedge = False
            for target_id, cover in bonuses.items():
                if target_id == self.state.inspected_token_id:
                    continue
                
                if not cover.segments:
                    continue
                
                # Apex in Screen Space
                ax, ay = cover.best_apex
                asx, asy = self.map_system.world_to_screen(ax * inv_scale, ay * inv_scale)
                apex_screen = (int(asx), int(asy))
                
            drawn_any_wedge = False
            for target_id, cover in bonuses.items():
                if target_id == self.state.inspected_token_id:
                    continue
                
                if not cover.segments:
                    continue
                
                # Apex in Screen Space
                ax, ay = cover.best_apex
                asx, asy = self.map_system.world_to_screen(ax * inv_scale, ay * inv_scale)
                apex_screen = (int(asx), int(asy))
                
                all_visible_pts = []
                
                # Target Center in Screen Space (to pinch the polygons and determine radius)
                all_tokens = self.state.tokens + [t for t in self.map_system.ghost_tokens if t.id not in {tk.id for tk in self.state.tokens}]
                target_tk = next((t for t in all_tokens if t.id == target_id), None)
                if target_tk:
                    tsx, tsy = self.map_system.world_to_screen(target_tk.world_x, target_tk.world_y)
                    target_center_screen = (int(tsx), int(tsy))
                else:
                    target_center_screen = None

                for seg in cover.segments:
                    # 1. Determine Angular Span from sorted npc_pixels
                    # (Note: npc_pixels are already angularly sorted relative to best_apex)
                    p_start = cover.npc_pixels[seg.start_idx]
                    p_end = cover.npc_pixels[seg.end_idx]
                    
                    # Convert mask coords back to world then to screen relative vectors
                    asx_px, asy_px = cover.best_apex
                    
                    # Vector relative to Apex
                    vec_start = np.array(p_start) - np.array([asx_px, asy_px])
                    vec_end = np.array(p_end) - np.array([asx_px, asy_px])
                    
                    ang_start = math.atan2(vec_start[1], vec_start[0])
                    ang_end = math.atan2(vec_end[1], vec_end[0])
                    
                    # 2. Determine Radius
                    # Use distance from apex to target center for a consistent "radar sweep" length
                    if target_center_screen:
                        dist = math.sqrt((apex_screen[0]-target_center_screen[0])**2 + (apex_screen[1]-target_center_screen[1])**2)
                    else:
                        # Fallback: boundary point distance
                        psx_s, psy_s = self.map_system.world_to_screen(p_start[0] * inv_scale, p_start[1] * inv_scale)
                        dist = math.sqrt((apex_screen[0]-psx_s)**2 + (apex_screen[1]-psy_s)**2)
                    
                    # 3. Build smooth arc for the sector
                    # Using 20 points for a very smooth high-res curve
                    num_arc_pts = 20
                    arc_pts = []
                    
                    # Handle wrap-around for interpolation
                    diff = ang_end - ang_start
                    while diff > math.pi:
                        diff -= 2 * math.pi
                    while diff < -math.pi:
                        diff += 2 * math.pi
                    ang_end_interp = ang_start + diff
                    
                    for i in range(num_arc_pts + 1):
                        t = i / num_arc_pts
                        a = ang_start + t * (ang_end_interp - ang_start)
                        px = apex_screen[0] + dist * math.cos(a)
                        py = apex_screen[1] + dist * math.sin(a)
                        arc_pts.append([px, py])
                        all_visible_pts.append([px, py])
                    
                    # A pure circular sector polygon is [Apex, P1, P2, ..., PN]
                    poly_points = [apex_screen] + arc_pts
                    pts = np.array(poly_points, dtype=np.int32).reshape((-1, 1, 2))
                    
                    if seg.status == 0:  # Clear
                        cv2.fillPoly(wedge_img, [pts], (255, 255, 0, 80))
                    elif seg.status == 2:  # Obscured
                        wedge_mask = np.zeros((screen_h, screen_w), dtype=np.uint8)
                        cv2.fillPoly(wedge_mask, [pts], 255)
                        final_stipple = cv2.bitwise_and(wedge_mask, stipple_mask)
                        wedge_img[final_stipple > 0] = (255, 255, 0, 200)

                # Draw the two outermost edges of the entire cone
                if cover.segments:
                    # The first point of the first segment and last point of last segment
                    # are the true extreme edges because npc_pixels is already sorted/rotated.
                    p_start_edge = cover.npc_pixels[cover.segments[0].start_idx]
                    p_end_edge = cover.npc_pixels[cover.segments[-1].end_idx]
                    
                    psx1, psy_1 = self.map_system.world_to_screen(p_start_edge[0] * inv_scale, p_start_edge[1] * inv_scale)
                    psx2, psy_2 = self.map_system.world_to_screen(p_end_edge[0] * inv_scale, p_end_edge[1] * inv_scale)
                    
                    p_edge1 = (int(psx1), int(psy_1))
                    p_edge2 = (int(psx2), int(psy_2))
                    
                    cv2.line(wedge_img, apex_screen, p_edge1, (255, 255, 255, 255), 2)
                    cv2.line(wedge_img, apex_screen, p_edge2, (255, 255, 255, 255), 2)
                    drawn_any_wedge = True
            
            if drawn_any_wedge:
                patches.append(
                    ImagePatch(x=0, y=0, width=screen_w, height=screen_h, data=wedge_img)
                )

        # 2. Render Tactical Labels
        # Access tactical bonuses from dedicated state map
        bonuses = self.state.tactical_bonuses

        # Combine tokens for rendering
        all_tokens = []
        all_tokens.extend(self.state.tokens)
        existing_ids = {t.id for t in all_tokens}
        all_tokens.extend(
            [t for t in self.map_system.ghost_tokens if t.id not in existing_ids]
        )

        ppi = self.map_system.config.projector_ppi if self.map_system.config else 96.0

        for token in all_tokens:
            if token.id == self.state.inspected_token_id:
                continue

            # Retrieve bonuses for this token
            cover = bonuses.get(token.id)
            if cover is None:
                continue
            
            ac_bonus = cover.ac_bonus
            reflex_bonus = cover.reflex_bonus

            # Determine label text and color
            if ac_bonus == -1:
                label = "TOTAL COVER"
                color = (0, 0, 255)  # Red
            elif ac_bonus > 0 or reflex_bonus > 0:
                label = f"+{ac_bonus} AC / +{reflex_bonus} Reflex"
                color = (0, 255, 0)  # Green
            else:
                label = "CLEAR LOS"
                color = (255, 255, 0)  # Cyan (BGR)

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

            # Calculate screen coordinates
            sx, sy = self.map_system.world_to_screen(token.world_x, token.world_y)

            # Determine offset to place label BELOW the token circle
            # Tokens are typically 1 inch diameter (PPI pixels)
            radius = ppi / 2

            patches.append(
                ImagePatch(
                    x=int(sx - patch_w // 2),
                    y=int(sy + radius + 5),
                    width=patch_w,
                    height=lh,
                    data=text_img[:lh, :patch_w].copy(),
                )
            )

        return patches
