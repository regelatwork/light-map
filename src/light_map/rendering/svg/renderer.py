import svgelements
import numpy as np
import cv2
import base64
from io import BytesIO
from typing import List, Tuple
from PIL import Image
from light_map.rendering.svg.utils import get_element_opacity
from light_map.rendering.svg.geometry import convert_path_to_points


def render_image_element(
    element: svgelements.Image,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
    render_w: int,
    render_h: int,
):
    """Renders a raster image element into the BGR buffer."""
    pil_img = element.image

    if pil_img is None:
        href = (
            element.values.get("href")
            or element.values.get("xlink:href")
            or element.values.get("{http://www.w3.org/1999/xlink}href")
        )
        if href and href.startswith("data:image/"):
            try:
                header, data = href.split(",", 1)
                image_data = base64.b64decode(data)
                pil_img = Image.open(BytesIO(image_data))
            except Exception:
                pass

    if pil_img:
        # Keep alpha if present
        pil_img = pil_img.convert("RGBA")
        src_img = np.array(pil_img)
        # Convert RGBA to BGRA
        src_img = cv2.cvtColor(src_img, cv2.COLOR_RGBA2BGRA)

        img_h, img_w = src_img.shape[:2]
        target_w = element.width or img_w
        target_h = element.height or img_h
        target_x = element.x or 0
        target_y = element.y or 0

        local_m = svgelements.Matrix()
        local_m.post_scale(target_w / img_w, target_h / img_h)
        local_m.post_translate(target_x, target_y)

        if element.transform:
            local_m = local_m * element.transform

        final_m = local_m * final_vp_matrix
        M = np.float32(
            [[final_m.a, final_m.c, final_m.e], [final_m.b, final_m.d, final_m.f]]
        )
        # warpAffine handles 4 channels (BGRA) correctly
        warped_bgra = cv2.warpAffine(src_img, M, (render_w, render_h))

        # Separate BGR and Alpha
        warped_bgr = warped_bgra[:, :, :3]
        warped_alpha = warped_bgra[:, :, 3]

        # Standard alpha blending
        # Normalize alpha to 0.0 - 1.0
        alpha_f = warped_alpha.astype(float) / 255.0
        alpha_f = alpha_f[:, :, np.newaxis]  # Broad-castable to BGR

        # Blend: dst = src * alpha + dst * (1 - alpha)
        # Note: image is the BGR buffer we are rendering into
        image[:] = (warped_bgr.astype(float) * alpha_f + image.astype(float) * (1.0 - alpha_f)).astype(np.uint8)


def render_text_element(
    element: svgelements.Text,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
):
    """Renders a text element into the BGR buffer."""
    text_str = element.text
    if not text_str:
        return

    tx, ty = element.x or 0, element.y or 0
    p = final_vp_matrix.point_in_matrix_space((tx, ty))
    render_x, render_y = int(p.x), int(p.y)

    color = (255, 255, 255)
    if element.fill is not None and element.fill.value is not None:
        c = element.fill
        color = (c.blue, c.green, c.red)

    svg_font_size = element.font_size or 12
    avg_scale = (abs(final_vp_matrix.a) + abs(final_vp_matrix.d)) / 2
    cv_scale = (svg_font_size * avg_scale) / 25.0

    cv2.putText(
        image,
        text_str,
        (render_x, render_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        cv_scale,
        color,
        thickness=max(1, int(avg_scale)),
        lineType=cv2.LINE_AA,
    )


def apply_fill(
    element: svgelements.Shape,
    image: np.ndarray,
    all_subpaths: List[np.ndarray],
    element_opacity: float,
):
    """Applies fill styling to subpaths."""
    if element.fill is None or element.fill.value is None:
        return
    c = element.fill
    fill_color = (c.blue, c.green, c.red)
    fill_opacity = element_opacity * float(getattr(c, "opacity", 1.0) or 1.0)

    if fill_opacity >= 0.99:
        cv2.fillPoly(image, all_subpaths, fill_color)
    elif fill_opacity > 0:
        overlay = image.copy()
        cv2.fillPoly(overlay, all_subpaths, fill_color)
        cv2.addWeighted(overlay, fill_opacity, image, 1.0 - fill_opacity, 0, image)


def draw_dashed_polyline(
    image: np.ndarray,
    polyline: np.ndarray,
    color: Tuple[int, int, int],
    thickness: int,
    dash_array: List[float],
    is_closed: bool = False,
):
    """Draws a dashed polyline using OpenCV."""
    if not dash_array:
        cv2.polylines(image, [polyline], is_closed, color, thickness)
        return

    # Flatten the points from (N, 1, 2) to (N, 2)
    pts = polyline.reshape(-1, 2)
    if is_closed:
        pts = np.vstack([pts, pts[0]])

    dash_idx = 0
    dash_remaining = dash_array[0]
    dash_state = True  # True = Draw, False = Gap

    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]
        vec = p2 - p1
        segment_len = np.linalg.norm(vec)
        if segment_len < 1e-6:
            continue

        unit_vec = vec / segment_len
        dist_traversed = 0.0

        while dist_traversed < segment_len:
            draw_len = min(segment_len - dist_traversed, dash_remaining)
            if dash_state:
                start_pt = p1 + unit_vec * dist_traversed
                end_pt = start_pt + unit_vec * draw_len
                cv2.line(
                    image,
                    tuple(start_pt.astype(int)),
                    tuple(end_pt.astype(int)),
                    color,
                    thickness,
                )

            dist_traversed += draw_len
            dash_remaining -= draw_len

            if dash_remaining < 1e-6:
                dash_idx = (dash_idx + 1) % len(dash_array)
                dash_remaining = dash_array[dash_idx]
                dash_state = not dash_state


def apply_stroke(
    element: svgelements.Shape,
    image: np.ndarray,
    closed_subpaths: List[np.ndarray],
    open_subpaths: List[np.ndarray],
    final_vp_matrix: svgelements.Matrix,
    element_opacity: float,
):
    """Applies stroke styling to subpaths."""
    if element.stroke is None or element.stroke.value is None:
        return
    c = element.stroke
    color = (c.blue, c.green, c.red)
    if sum(color) < 30:
        color = (255, 255, 255)

    stroke_opacity = element_opacity * float(getattr(c, "opacity", 1.0) or 1.0)
    thickness = 1
    avg_scale = (abs(final_vp_matrix.a) + abs(final_vp_matrix.d)) / 2
    if element.stroke_width is not None:
        thickness = max(1, int(element.stroke_width * avg_scale))

    # Dash support
    dash_array = []
    if "stroke-dasharray" in element.values:
        try:
            val = str(element.values["stroke-dasharray"])
            # Split by comma or space
            parts = val.replace(",", " ").split()
            dash_array = [float(p) * avg_scale for p in parts if p.strip()]
            # If odd number of elements, SVG specs say repeat it
            if len(dash_array) % 2 == 1:
                dash_array.extend(dash_array)
        except (ValueError, TypeError):
            dash_array = []

    def draw_all(img_target, alpha):
        for sub in closed_subpaths:
            if dash_array:
                draw_dashed_polyline(
                    img_target, sub, color, thickness, dash_array, is_closed=True
                )
            else:
                cv2.polylines(img_target, [sub], True, color, thickness)
        for sub in open_subpaths:
            if dash_array:
                draw_dashed_polyline(
                    img_target, sub, color, thickness, dash_array, is_closed=False
                )
            else:
                cv2.polylines(img_target, [sub], False, color, thickness)

    if stroke_opacity >= 0.99:
        draw_all(image, 1.0)
    elif stroke_opacity > 0:
        overlay = image.copy()
        draw_all(overlay, stroke_opacity)
        cv2.addWeighted(overlay, stroke_opacity, image, 1.0 - stroke_opacity, 0, image)


def render_shape_element(
    element: svgelements.Shape,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
    scale_factor: float,
    quality: float,
):
    """Renders a shape element (Path, Rect, etc.) into the BGR buffer."""
    # Elements that are intrinsically closed
    element_naturally_closed = isinstance(
        element,
        (
            svgelements.Rect,
            svgelements.Circle,
            svgelements.Ellipse,
            svgelements.Polygon,
        ),
    )

    ppu = (scale_factor * quality) * 0.5
    path = svgelements.Path(element)
    transformed_path = path * final_vp_matrix
    transformed_path.reify()
    closed, open_paths = convert_path_to_points(
        transformed_path, element_naturally_closed, ppu
    )

    all_subpaths = closed + open_paths
    if not all_subpaths:
        return

    opacity = get_element_opacity(element)
    apply_fill(element, image, all_subpaths, opacity)
    apply_stroke(element, image, closed, open_paths, final_vp_matrix, opacity)


def detect_grid_spacing_raster(svg: svgelements.SVG, render_func) -> float:
    """Renders the SVG and uses signal processing to find grid spacing."""
    target_w = 2048
    if svg.width <= 0 or svg.height <= 0:
        return 0.0

    aspect = svg.height / svg.width
    target_h = int(target_w * aspect)
    scale = target_w / svg.width

    img = render_func(
        target_w,
        target_h,
        scale_factor=scale,
        offset_x=target_w / 2 - (svg.width * scale) / 2,
        offset_y=target_h / 2 - (svg.height * scale) / 2,
        rotation=0,
        quality=1.0,
    )

    if img is None:
        return 0.0

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    def analyze_axis(axis_sum):
        n = len(axis_sum)
        if np.max(axis_sum) == 0:
            return 0.0
        signal = axis_sum / np.max(axis_sum)
        lags = np.arange(10, n // 2)
        corrs = [np.sum(signal[lag:] * signal[:-lag]) for lag in lags]
        return lags[np.argmax(corrs)] if corrs else 0.0

    px_spacing_x = analyze_axis(np.sum(edges, axis=0))
    px_spacing_y = analyze_axis(np.sum(edges, axis=1))

    spacings = [px / scale for px in [px_spacing_x, px_spacing_y] if px > 0]
    return sum(spacings) / len(spacings) if spacings else 0.0
