from typing import Any

import cv2
import numpy as np

from light_map.core.display_utils import draw_text_with_background


def generate_stereo_calibration_pattern(
    width: int,
    height: int,
    ppi: float = 96.0,
    token_names: dict[int, str] | None = None,
    token_heights: dict[int, float] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Generates the high-contrast projection pattern for Single-Sweep Stereo Calibration.

    Includes:
      - 8 ArUco grid markers (IDs 42-49) in a 2x4 grid at known 40mm physical tabletop coordinates (Z=0).
      - Placement boundary and marker guides for the physical PPI ruler sheet (IDs 40 & 41, 100mm span).
      - 4 illuminated corner target rings with token labels and expected heights (Z=50mm, IDs 0-3).

    Args:
        width: Canvas width in projector pixels.
        height: Canvas height in projector pixels.
        ppi: Projector pixels per inch (defaults to 96.0).
        token_names: Mapping of token ID to character name.
        token_heights: Mapping of token ID to physical height in mm.

    Returns:
        pattern_image: BGR numpy array containing the full projected scene.
        pattern_params: Metadata describing marker and target positions.
    """
    if token_names is None:
        token_names = {0: "Cricket", 1: "Lace", 2: "Shikra", 3: "Verita"}
    if token_heights is None:
        token_heights = {0: 50.0, 1: 50.0, 2: 50.0, 3: 50.0}

    scale = ppi / 25.4  # pixels per mm

    # 1. Canvas: High-contrast white background (BGR)
    img = np.full((height, width, 3), 255, dtype=np.uint8)

    # Dark framing border
    cv2.rectangle(img, (4, 4), (width - 5, height - 5), (60, 60, 60), 2)

    # 2. Center 2x4 Grid of ArUco Markers (IDs 42-49)
    # Spacing: 40mm between centers horizontally and vertically
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    grid_spacing_px = int(40.0 * scale)
    marker_size = max(20, int(24.0 * scale))  # Leaves 16mm spacing (8mm quiet zone)

    cx = width // 2
    cy = height // 2 - int(25.0 * scale)

    grid_markers_meta = []
    # Grid layout: Row 0 (42, 43, 44, 45), Row 1 (46, 47, 48, 49)
    # ox = (j - 1.5) * 40mm, oy = (i - 0.5) * 40mm
    for i in range(2):
        for j in range(4):
            mid = 42 + 4 * i + j
            ox_mm = (j - 1.5) * 40.0
            oy_mm = (i - 0.5) * 40.0
            mx = int(cx + ox_mm * scale)
            my = int(cy + oy_mm * scale)

            # Generate marker bits
            marker_raw = cv2.aruco.generateImageMarker(aruco_dict, mid, marker_size)
            marker_bgr = cv2.cvtColor(marker_raw, cv2.COLOR_GRAY2BGR)

            x1 = mx - marker_size // 2
            y1 = my - marker_size // 2
            x2 = x1 + marker_size
            y2 = y1 + marker_size

            # Paste into canvas
            if 0 <= x1 and x2 <= width and 0 <= y1 and y2 <= height:
                img[y1:y2, x1:x2] = marker_bgr

            # Label below marker
            label = f"ID {mid}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
            cv2.putText(
                img,
                label,
                (mx - tw // 2, y2 + th + 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (40, 40, 40),
                1,
                cv2.LINE_AA,
            )

            grid_markers_meta.append(
                {
                    "id": mid,
                    "center": (mx, my),
                    "size_px": marker_size,
                    "x_mm": ox_mm,
                    "y_mm": oy_mm,
                }
            )

    # Header above grid
    grid_title = "PROJECTED CALIBRATION GRID (IDs 42-49, 40mm SPAN, Z=0)"
    (gtw, gth), _ = cv2.getTextSize(grid_title, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    grid_top_y = cy - int(0.5 * grid_spacing_px) - marker_size // 2 - 16
    cv2.putText(
        img,
        grid_title,
        (cx - gtw // 2, grid_top_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (50, 50, 50),
        1,
        cv2.LINE_AA,
    )

    # 3. Physical PPI Ruler Sheet Guide (IDs 40 & 41)
    # Positioned below the grid
    ruler_cy = cy + int(85.0 * scale)
    ruler_dist_px = int(100.0 * scale)
    m40_x = cx - ruler_dist_px // 2
    m41_x = cx + ruler_dist_px // 2

    # Outline boundary for physical sheet (approx 140mm x 36mm)
    sheet_w = int(140.0 * scale)
    sheet_h = int(36.0 * scale)
    sx1 = cx - sheet_w // 2
    sy1 = ruler_cy - sheet_h // 2
    sx2 = sx1 + sheet_w
    sy2 = sy1 + sheet_h

    # Draw guide boundary with light gray fill and dashed border
    overlay = img.copy()
    cv2.rectangle(overlay, (sx1, sy1), (sx2, sy2), (240, 240, 240), -1)
    cv2.addWeighted(overlay, 0.8, img, 0.2, 0, img)
    cv2.rectangle(img, (sx1, sy1), (sx2, sy2), (120, 120, 120), 1)

    # Targets for markers 40 and 41
    target_box_size = marker_size
    for mid, tx in [(40, m40_x), (41, m41_x)]:
        bx1 = tx - target_box_size // 2
        by1 = ruler_cy - target_box_size // 2
        bx2 = bx1 + target_box_size
        by2 = by1 + target_box_size
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (80, 80, 80), 1)
        # Crosshair in target box
        cv2.line(img, (bx1, ruler_cy), (bx2, ruler_cy), (140, 140, 140), 1)
        cv2.line(img, (tx, by1), (tx, by2), (140, 140, 140), 1)
        # Label
        lbl = f"ID {mid}"
        (lw, lh), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
        cv2.putText(
            img,
            lbl,
            (tx - lw // 2, by2 + lh + 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (50, 50, 50),
            1,
            cv2.LINE_AA,
        )

    # Ruler sheet label
    ruler_lbl = "PLACE PHYSICAL PPI RULER (IDs 40 & 41) FLAT HERE - 100mm SPAN"
    (rlw, rlh), _ = cv2.getTextSize(ruler_lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
    cv2.putText(
        img,
        ruler_lbl,
        (cx - rlw // 2, sy1 - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (60, 60, 60),
        1,
        cv2.LINE_AA,
    )

    # 4. 4 Illuminated Corner Target Rings (IDs 0-3)
    # Positions in 4 screen quadrants with comfortable margins
    x_left = max(int(60.0 * scale), int(width * 0.16))
    x_right = min(width - int(60.0 * scale), int(width * 0.84))
    y_top = max(int(50.0 * scale), int(height * 0.22))
    y_bottom = min(height - int(50.0 * scale), int(height * 0.78))

    ring_positions = [
        (0, x_left, y_top),
        (1, x_right, y_top),
        (2, x_left, y_bottom),
        (3, x_right, y_bottom),
    ]

    ring_radius = max(28, int(18.0 * scale))
    token_targets_meta = []

    for tid, rx, ry in ring_positions:
        name = token_names.get(tid, f"Token {tid}")
        h_mm = token_heights.get(tid, 50.0)

        # Draw target ring: outer circle, inner circle, crosshairs
        cv2.circle(img, (rx, ry), ring_radius, (60, 60, 180), 2)  # Dark reddish/blue outer ring
        cv2.circle(img, (rx, ry), ring_radius // 2, (100, 100, 200), 1)

        ch = int(ring_radius * 1.35)
        cv2.line(img, (rx - ch, ry), (rx + ch, ry), (120, 120, 200), 1)
        cv2.line(img, (rx, ry - ch), (rx, ry + ch), (120, 120, 200), 1)

        # Labels
        t_label = f"Token {tid}: {name}"
        draw_text_with_background(
            img,
            t_label,
            (rx - ring_radius - 10, ry + ring_radius + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (30, 30, 30),
            1,
            bg_color=(230, 230, 230),
        )
        h_val = float(h_mm) if isinstance(h_mm, (int, float)) else 50.0
        sub_label = f"Elevated Ring (Z={h_val:.0f}mm)"
        draw_text_with_background(
            img,
            sub_label,
            (rx - ring_radius - 10, ry + ring_radius + 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (80, 80, 80),
            1,
            bg_color=(240, 240, 240),
        )

        token_targets_meta.append(
            {
                "id": tid,
                "name": name,
                "height_mm": h_mm,
                "x": rx,
                "y": ry,
                "radius": ring_radius,
                "shape": "ring",
            }
        )

    pattern_params = {
        "grid_markers": grid_markers_meta,
        "ruler_targets": {
            "m40": (m40_x, ruler_cy),
            "m41": (m41_x, ruler_cy),
            "distance_mm": 100.0,
            "rect": (sx1, sy1, sheet_w, sheet_h),
        },
        "token_targets": token_targets_meta,
    }

    return img, pattern_params
