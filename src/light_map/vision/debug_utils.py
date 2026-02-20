import cv2
import math
import numpy as np
from datetime import datetime

class DebugVisualizer:
    @staticmethod
    def draw_grid(debug_img, map_system, grid_spacing_svg, grid_origin_x, grid_origin_y):
        h, w = debug_img.shape[:2]
        grid_color = (100, 100, 100)
        
        # Find world bounds to draw enough lines
        p_top_left = map_system.screen_to_world(0, 0)
        p_top_right = map_system.screen_to_world(w, 0)
        p_bot_left = map_system.screen_to_world(0, h)
        p_bot_right = map_system.screen_to_world(w, h)
        
        min_wx = min(p_top_left[0], p_top_right[0], p_bot_left[0], p_bot_right[0])
        max_wx = max(p_top_left[0], p_top_right[0], p_bot_left[0], p_bot_right[0])
        min_wy = min(p_top_left[1], p_top_right[1], p_bot_left[1], p_bot_right[1])
        max_wy = max(p_top_left[1], p_top_right[1], p_bot_left[1], p_bot_right[1])

        # Draw vertical lines
        start_gx = int(math.floor((min_wx - grid_origin_x) / grid_spacing_svg))
        end_gx = int(math.ceil((max_wx - grid_origin_x) / grid_spacing_svg))
        for gx in range(start_gx, end_gx + 1):
            wx = grid_origin_x + gx * grid_spacing_svg
            p1_s = map_system.world_to_screen(wx, min_wy)
            p2_s = map_system.world_to_screen(wx, max_wy)
            cv2.line(
                debug_img,
                (int(p1_s[0]), int(p1_s[1])),
                (int(p2_s[0]), int(p2_s[1])),
                grid_color,
                1,
            )

        # Draw horizontal lines
        start_gy = int(math.floor((min_wy - grid_origin_y) / grid_spacing_svg))
        end_gy = int(math.ceil((max_wy - grid_origin_y) / grid_spacing_svg))
        for gy in range(start_gy, end_gy + 1):
            wy = grid_origin_y + gy * grid_spacing_svg
            p1_s = map_system.world_to_screen(min_wx, wy)
            p2_s = map_system.world_to_screen(max_wx, wy)
            cv2.line(
                debug_img,
                (int(p1_s[0]), int(p1_s[1])),
                (int(p2_s[0]), int(p2_s[1])),
                grid_color,
                1,
            )

    @staticmethod
    def draw_tokens(debug_img, tokens, map_system):
        for token in tokens:
            sx, sy = map_system.world_to_screen(token.world_x, token.world_y)
            cv2.circle(debug_img, (int(sx), int(sy)), 20, (0, 255, 255), 2)
            
    @staticmethod
    def save_debug_image(filename_prefix, debug_img):
        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        cv2.imwrite(filename, debug_img)
