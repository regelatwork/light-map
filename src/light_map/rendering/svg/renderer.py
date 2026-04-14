import svgelements
import numpy as np
import cv2
import base64
from io import BytesIO
from typing import List, Tuple
from PIL import Image
from light_map.rendering.svg.utils import get_element_opacity
from light_map.rendering.svg.geometry import convert_path_to_points


def blend_bgra(dst: np.ndarray, src_bgra: np.ndarray):
    """Blends a BGRA image onto a BGR or BGRA target."""
    src_rgb = src_bgra[:, :, :3].astype(float)
    src_a = src_bgra[:, :, 3].astype(float) / 255.0
    src_a_3 = src_a[:, :, np.newaxis]

    if dst.shape[2] == 3:
        dst[:] = (src_rgb * src_a_3 + dst.astype(float) * (1.0 - src_a_3)).astype(
            np.uint8
        )
    else:
        # Full BGRA compositing
        dst_rgb = dst[:, :, :3].astype(float)
        dst_a = dst[:, :, 3].astype(float) / 255.0

        out_a = src_a + dst_a * (1.0 - src_a)
        # Avoid division by zero
        safe_out_a = np.where(out_a > 0, out_a, 1.0)

        for c in range(3):
            dst[:, :, c] = (
                (
                    src_rgb[:, :, c] * src_a
                    + dst_rgb[:, :, c] * dst_a * (1.0 - src_a)
                )
                / safe_out_a
            ).astype(np.uint8)
        dst[:, :, 3] = (out_a * 255.0).astype(np.uint8)


def render_image_element(
    element: svgelements.Image,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
    render_w: int,
    render_h: int,
    svg: svgelements.SVG,
):
    """Renders a raster image element into the BGR or BGRA buffer."""
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

        if image.shape[2] == 3:
            # Separate BGR and Alpha
            warped_bgr = warped_bgra[:, :, :3]
            warped_alpha = warped_bgra[:, :, 3]
            alpha_f = warped_alpha.astype(float) / 255.0
            alpha_f = alpha_f[:, :, np.newaxis]
            image[:] = (
                warped_bgr.astype(float) * alpha_f
                + image.astype(float) * (1.0 - alpha_f)
            ).astype(np.uint8)
        else:
            blend_bgra(image, warped_bgra)


def render_text_element(
    element: svgelements.Text,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
    svg: svgelements.SVG,
):
    """Renders a text element into the BGR or BGRA buffer."""
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

    if image.shape[2] == 4:
        opacity = get_element_opacity(element)
        color_alpha = (color[0], color[1], color[2], int(opacity * 255))
        cv2.putText(
            image,
            text_str,
            (render_x, render_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            cv_scale,
            color_alpha,
            thickness=max(1, int(avg_scale)),
            lineType=cv2.LINE_AA,
        )
    else:
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
    svg: svgelements.SVG,
    final_vp_matrix: svgelements.Matrix,
):
    """Applies fill styling to subpaths."""
    fill_val = element.values.get("fill")
    if fill_val and fill_val.startswith("url(#"):
        gradient_id = fill_val[5:-1]
        gradient_elem = svg.get_element_by_id(gradient_id)
        if gradient_elem:
            tag = gradient_elem.values.get("tag")
            if tag == "radialGradient":
                render_radial_gradient(
                    image,
                    all_subpaths,
                    gradient_elem,
                    svg,
                    final_vp_matrix,
                    element_opacity,
                )
                return
            elif tag == "linearGradient":
                render_linear_gradient(
                    image,
                    all_subpaths,
                    gradient_elem,
                    svg,
                    final_vp_matrix,
                    element_opacity,
                )
                return

    if element.fill is None or element.fill.value is None:
        return
    c = element.fill
    fill_color = (c.blue, c.green, c.red)
    fill_opacity = element_opacity * float(getattr(c, "opacity", 1.0) or 1.0)

    if image.shape[2] == 4:
        color_alpha = (
            fill_color[0],
            fill_color[1],
            fill_color[2],
            int(fill_opacity * 255),
        )
        if fill_opacity >= 0.99:
            cv2.fillPoly(image, all_subpaths, color_alpha)
        else:
            overlay = np.zeros_like(image)
            cv2.fillPoly(overlay, all_subpaths, color_alpha)
            blend_bgra(image, overlay)
    else:
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
    svg: svgelements.SVG,
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

    if image.shape[2] == 4:
        color_alpha = (color[0], color[1], color[2], int(stroke_opacity * 255))
        if stroke_opacity >= 0.99:
            for sub in closed_subpaths:
                cv2.polylines(image, [sub], True, color_alpha, thickness)
            for sub in open_subpaths:
                cv2.polylines(image, [sub], False, color_alpha, thickness)
        else:
            overlay = np.zeros_like(image)
            for sub in closed_subpaths:
                cv2.polylines(overlay, [sub], True, color_alpha, thickness)
            for sub in open_subpaths:
                cv2.polylines(overlay, [sub], False, color_alpha, thickness)
            blend_bgra(image, overlay)
    else:

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
            cv2.addWeighted(
                overlay, stroke_opacity, image, 1.0 - stroke_opacity, 0, image
            )


def render_linear_gradient(
    image: np.ndarray,
    all_subpaths: List[np.ndarray],
    gradient_elem: svgelements.Group,
    svg: svgelements.SVG,
    final_vp_matrix: svgelements.Matrix,
    element_opacity: float,
):
    """Renders a linear gradient into the shape defined by all_subpaths."""
    stops = get_gradient_stops(gradient_elem, svg)
    if not stops:
        return

    # Gradient parameters
    try:
        x1 = (
            float(str(gradient_elem.values.get("x1", "0%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("x1", "0%"))
            else float(gradient_elem.values.get("x1", "0"))
        )
        y1 = (
            float(str(gradient_elem.values.get("y1", "0%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("y1", "0%"))
            else float(gradient_elem.values.get("y1", "0"))
        )
        x2 = (
            float(str(gradient_elem.values.get("x2", "100%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("x2", "100%"))
            else float(gradient_elem.values.get("x2", "1"))
        )
        y2 = (
            float(str(gradient_elem.values.get("y2", "0%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("y2", "0%"))
            else float(gradient_elem.values.get("y2", "0"))
        )
    except (ValueError, TypeError):
        return

    # Gradient Transform
    g_transform = svgelements.Matrix(gradient_elem.values.get("gradientTransform", ""))
    # Include any inherited transform (e.g. from root SVG or defs)
    inherited_transform = svgelements.Matrix(gradient_elem.values.get("transform", ""))
    g_transform = inherited_transform * g_transform

    # Combined inverse matrix: From screen to gradient space
    try:
        inv_matrix = ~(g_transform * final_vp_matrix)
    except Exception:
        return

    # Shape mask
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, all_subpaths, 255)

    y_idx, x_idx = np.where(mask > 0)
    if len(x_idx) == 0:
        return

    pts = np.stack((x_idx, y_idx), axis=-1).astype(float)
    # Transform points to gradient space
    gx = pts[:, 0] * inv_matrix.a + pts[:, 1] * inv_matrix.c + inv_matrix.e
    gy = pts[:, 0] * inv_matrix.b + pts[:, 1] * inv_matrix.d + inv_matrix.f

    # Project onto line (x1,y1) to (x2,y2)
    # Vector from (x1,y1) to (gx,gy)
    v_gx = gx - x1
    v_gy = gy - y1
    # Vector from (x1,y1) to (x2,y2)
    v_dx = x2 - x1
    v_dy = y2 - y1
    v_d_mag2 = v_dx**2 + v_dy**2

    if v_d_mag2 < 1e-6:
        t = np.zeros_like(gx)
    else:
        # Projection: t = (v_g dot v_d) / |v_d|^2
        t = (v_gx * v_dx + v_gy * v_dy) / v_d_mag2

    t = np.clip(t, 0, 1)

    # Interpolate colors
    final_colors = np.zeros((len(t), 4), dtype=np.float32)
    if len(stops) == 1:
        final_colors[:] = stops[0][1]
    else:
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            mask_range = (t >= t0) & (t <= t1)
            if np.any(mask_range):
                interp_t = (t[mask_range] - t0) / (t1 - t0)
                final_colors[mask_range] = c0 + interp_t[:, np.newaxis] * (c1 - c0)
        # Handle values outside range
        final_colors[t < stops[0][0]] = stops[0][1]
        final_colors[t > stops[-1][0]] = stops[-1][1]

    # Apply element opacity
    final_colors[:, 3] *= element_opacity

    # Alpha blending
    if image.shape[2] == 3:
        alpha = final_colors[:, 3:4] / 255.0
        fg = final_colors[:, :3]
        bg = image[y_idx, x_idx].astype(np.float32)
        image[y_idx, x_idx] = (fg * alpha + bg * (1.0 - alpha)).astype(np.uint8)
    else:
        # Full BGRA blend onto subset of pixels
        src_rgb = final_colors[:, :3]
        src_a = final_colors[:, 3] / 255.0

        dst_rgb = image[y_idx, x_idx, :3].astype(float)
        dst_a = image[y_idx, x_idx, 3].astype(float) / 255.0

        out_a = src_a + dst_a * (1.0 - src_a)
        safe_out_a = np.where(out_a > 0, out_a, 1.0)

        for c in range(3):
            image[y_idx, x_idx, c] = (
                (src_rgb[:, c] * src_a + dst_rgb[:, c] * dst_a * (1.0 - src_a))
                / safe_out_a
            ).astype(np.uint8)
        image[y_idx, x_idx, 3] = (out_a * 255.0).astype(np.uint8)


def get_gradient_stops(gradient_elem: svgelements.Group, svg: svgelements.SVG):
    """Resolves stops for a gradient, including xlink:href references."""
    stops = []

    # Check for xlink:href
    href = gradient_elem.values.get("xlink:href") or gradient_elem.values.get(
        "{http://www.w3.org/1999/xlink}href"
    )
    if href and href.startswith("#"):
        ref_id = href[1:]
        ref_elem = svg.get_element_by_id(ref_id)
        if ref_elem and isinstance(ref_elem, svgelements.Group):
            stops.extend(get_gradient_stops(ref_elem, svg))

    # Add current stops
    for child in gradient_elem:
        if child.values.get("tag") == "stop":
            offset_str = str(child.values.get("offset", "0"))
            if offset_str.endswith("%"):
                offset = float(offset_str[:-1]) / 100.0
            else:
                offset = float(offset_str)

            style = child.values.get("style", "")
            stop_color = child.values.get("stop-color", "black")
            stop_opacity = float(child.values.get("stop-opacity", 1.0))

            if style:
                for part in style.split(";"):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        if k.strip() == "stop-color":
                            stop_color = v.strip()
                        elif k.strip() == "stop-opacity":
                            try:
                                stop_opacity = float(v.strip())
                            except ValueError:
                                pass

            color = svgelements.Color(stop_color)
            stops.append(
                (
                    offset,
                    np.array(
                        [color.blue, color.green, color.red, int(stop_opacity * 255)],
                        dtype=np.float32,
                    ),
                )
            )

    stops.sort(key=lambda x: x[0])
    return stops


def render_radial_gradient(
    image: np.ndarray,
    all_subpaths: List[np.ndarray],
    gradient_elem: svgelements.Group,
    svg: svgelements.SVG,
    final_vp_matrix: svgelements.Matrix,
    element_opacity: float,
):
    """Renders a radial gradient into the shape defined by all_subpaths."""
    stops = get_gradient_stops(gradient_elem, svg)
    if not stops:
        return

    # Gradient parameters
    try:
        cx = (
            float(str(gradient_elem.values.get("cx", "50%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("cx", "50%"))
            else float(gradient_elem.values.get("cx", "0"))
        )
        cy = (
            float(str(gradient_elem.values.get("cy", "50%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("cy", "50%"))
            else float(gradient_elem.values.get("cy", "0"))
        )
        r = (
            float(str(gradient_elem.values.get("r", "50%")).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("r", "50%"))
            else float(gradient_elem.values.get("r", "0"))
        )
        fx = (
            float(str(gradient_elem.values.get("fx", str(cx))).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("fx", str(cx)))
            else float(gradient_elem.values.get("fx", str(cx)))
        )
        fy = (
            float(str(gradient_elem.values.get("fy", str(cy))).strip("%")) / 100.0
            if "%" in str(gradient_elem.values.get("fy", str(cy)))
            else float(gradient_elem.values.get("fy", str(cy)))
        )
    except (ValueError, TypeError):
        return

    # Gradient Transform
    g_transform = svgelements.Matrix(gradient_elem.values.get("gradientTransform", ""))
    # Include any inherited transform (e.g. from root SVG or defs)
    inherited_transform = svgelements.Matrix(gradient_elem.values.get("transform", ""))
    g_transform = inherited_transform * g_transform

    # Combined inverse matrix: From screen to gradient space
    try:
        inv_matrix = ~(g_transform * final_vp_matrix)
    except Exception:
        return

    # Shape mask
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, all_subpaths, 255)

    y_idx, x_idx = np.where(mask > 0)
    if len(x_idx) == 0:
        return

    pts = np.stack((x_idx, y_idx), axis=-1).astype(float)
    # Transform points to gradient space
    gx = pts[:, 0] * inv_matrix.a + pts[:, 1] * inv_matrix.c + inv_matrix.e
    gy = pts[:, 0] * inv_matrix.b + pts[:, 1] * inv_matrix.d + inv_matrix.f

    # Simple radial gradient: distance from (cx, cy)
    dist = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)
    t = np.clip(dist / r, 0, 1)

    # Interpolate colors
    final_colors = np.zeros((len(t), 4), dtype=np.float32)
    if len(stops) == 1:
        final_colors[:] = stops[0][1]
    else:
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            mask_range = (t >= t0) & (t <= t1)
            if np.any(mask_range):
                interp_t = (t[mask_range] - t0) / (t1 - t0)
                final_colors[mask_range] = c0 + interp_t[:, np.newaxis] * (c1 - c0)
        # Handle values outside range
        final_colors[t < stops[0][0]] = stops[0][1]
        final_colors[t > stops[-1][0]] = stops[-1][1]

    # Apply element opacity
    final_colors[:, 3] *= element_opacity

    # Alpha blending
    if image.shape[2] == 3:
        alpha = final_colors[:, 3:4] / 255.0
        fg = final_colors[:, :3]
        bg = image[y_idx, x_idx].astype(np.float32)
        image[y_idx, x_idx] = (fg * alpha + bg * (1.0 - alpha)).astype(np.uint8)
    else:
        # Full BGRA blend onto subset of pixels
        src_rgb = final_colors[:, :3]
        src_a = final_colors[:, 3] / 255.0

        dst_rgb = image[y_idx, x_idx, :3].astype(float)
        dst_a = image[y_idx, x_idx, 3].astype(float) / 255.0

        out_a = src_a + dst_a * (1.0 - src_a)
        safe_out_a = np.where(out_a > 0, out_a, 1.0)

        for c in range(3):
            image[y_idx, x_idx, c] = (
                (src_rgb[:, c] * src_a + dst_rgb[:, c] * dst_a * (1.0 - src_a))
                / safe_out_a
            ).astype(np.uint8)
        image[y_idx, x_idx, 3] = (out_a * 255.0).astype(np.uint8)


def render_shape_element(
    element: svgelements.Shape,
    image: np.ndarray,
    final_vp_matrix: svgelements.Matrix,
    scale_factor: float,
    quality: float,
    svg: svgelements.SVG,
):
    """Renders a shape element (Path, Rect, etc.) into the BGR or BGRA buffer."""
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
    apply_fill(element, image, all_subpaths, opacity, svg, final_vp_matrix)
    apply_stroke(element, image, closed, open_paths, final_vp_matrix, opacity, svg)


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
