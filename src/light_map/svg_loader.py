import svgelements
import numpy as np
import cv2
import math
import base64
import logging
from io import BytesIO
from typing import List, Tuple, Optional
from PIL import Image
import functools
from collections import Counter
from .visibility_types import VisibilityType, VisibilityBlocker


class SVGLoader:
    def __init__(self, filename: str):
        """
        Initialize the SVG loader.

        Args:
            filename: Path to the .svg file.
        """
        import os

        self.filename = os.path.abspath(filename)
        try:
            # Parse SVG with explicit unit scaling (defaulting to 96 DPI)
            self.svg = svgelements.SVG.parse(self.filename)
        except Exception as e:
            logging.error("Error loading SVG: %s", e)
            self.svg = None

    def detect_grid_spacing(self) -> tuple[float, float, float]:
        """
        Analyzes the SVG geometry to find the most likely grid spacing and origin.
        Returns (spacing, origin_x, origin_y) in SVG units.
        Returns (0.0, 0.0, 0.0) if no grid detected.
        """
        if not self.svg:
            return 0.0, 0.0, 0.0

        x_coords = []
        y_coords = []

        # Iterate through elements to find lines
        for element in self.svg.elements():
            if isinstance(element, svgelements.Path):
                # Decompose path into segments
                for segment in element:
                    if isinstance(segment, svgelements.Line):
                        p1 = segment.start
                        p2 = segment.end

                        # Check for vertical line
                        if abs(p1.x - p2.x) < 0.1 and abs(p1.y - p2.y) > 10:
                            x_coords.append(p1.x)
                        # Check for horizontal line
                        elif abs(p1.y - p2.y) < 0.1 and abs(p1.x - p2.x) > 10:
                            y_coords.append(p1.y)

            elif isinstance(element, svgelements.Rect):
                # Rects contribute 2 vertical and 2 horizontal lines
                x_coords.extend([element.x, element.x + element.width])
                y_coords.extend([element.y, element.y + element.height])

            elif isinstance(element, (svgelements.Line, svgelements.SimpleLine)):
                # SimpleLine uses x1, y1, x2, y2. Line uses start, end.
                if hasattr(element, "x1"):
                    p1x, p1y = element.x1, element.y1
                    p2x, p2y = element.x2, element.y2
                else:
                    p1x, p1y = element.start.x, element.start.y
                    p2x, p2y = element.end.x, element.end.y

                if abs(p1x - p2x) < 0.1:
                    x_coords.append(p1x)
                elif abs(p1y - p2y) < 0.1:
                    y_coords.append(p1y)

        # Filter and sort
        def find_spacing_and_origin(coords):
            if not coords:
                return 0.0, 0.0

            # Round to nearest 0.1 to handle float errors
            sorted_coords = sorted([round(c, 1) for c in coords])
            unique_coords = sorted(list(set(sorted_coords)))

            if len(unique_coords) < 3:
                return 0.0, 0.0

            # Calculate gaps
            gaps = []
            for i in range(len(unique_coords) - 1):
                gap = unique_coords[i + 1] - unique_coords[i]
                if gap > 1.0:  # Ignore tiny gaps
                    gaps.append(round(gap, 1))

            if not gaps:
                return 0.0, 0.0

            # Find mode
            counts = Counter(gaps)
            most_common = counts.most_common(1)
            if not most_common:
                return 0.0, 0.0

            mode_gap, count = most_common[0]

            # Heuristic: The mode must appear at least twice (3 lines)
            if count < 2:
                return 0.0, 0.0

            # Origin is the first coordinate
            origin = unique_coords[0]

            return mode_gap, origin

        spacing_x, origin_x = find_spacing_and_origin(x_coords)
        spacing_y, origin_y = find_spacing_and_origin(y_coords)

        # If both found, return average if close, otherwise X
        if spacing_x > 0 and spacing_y > 0:
            if abs(spacing_x - spacing_y) < 1.0:
                spacing = (spacing_x + spacing_y) / 2
            else:
                spacing = spacing_x  # Prefer X
        else:
            spacing = max(spacing_x, spacing_y)

        if spacing > 0:
            return spacing, origin_x, origin_y

        # Fallback: Raster Analysis (does not support origin detection)
        raster_spacing = self._detect_grid_spacing_raster()
        if raster_spacing > 0:
            return raster_spacing, 0.0, 0.0

        return 0.0, 0.0, 0.0

    def _detect_grid_spacing_raster(self) -> float:
        """
        Renders the SVG and uses signal processing to find grid spacing.
        """
        # Render at high resolution to ensure grid lines are sharp
        # Fixed width of 2048 seems reasonable
        target_w = 2048
        if self.svg.width <= 0 or self.svg.height <= 0:
            return 0.0

        aspect = self.svg.height / self.svg.width
        target_h = int(target_w * aspect)

        # Scale factor needed to fit SVG into target_w
        scale = target_w / self.svg.width

        # We can use our render method, but we need to ensure it renders everything
        # Our render method takes target width/height and fits viewport.
        # If we pass scale_factor=1.0, render() scales based on 'quality' to target dims?
        # No, render() logic:
        # vp_matrix.post_scale(scale_factor, scale_factor)
        # q_matrix.post_scale(quality, quality)
        # final = vp_matrix * q_matrix

        # We want to render the WHOLE SVG at resolution (target_w, target_h).
        # So we should pass scale_factor that maps SVG units to pixels.
        # But render() takes a 'scale_factor' argument which is the USER zoom.
        # And it centers it?

        # Let's use internal _render_internal directly or setup render params carefully.
        # render() method:
        # cx, cy = target_width / 2, ...
        # vp_matrix.post_rotate(..., cx, cy)
        # vp_matrix.post_translate(offset_x, offset_y)

        # If we want 1:1 mapping scaled by 'scale', we set scale_factor = scale.
        # And offset to center it?
        # Actually, let's just use the fact that render() renders the viewport.
        # If we want the whole map, we need to center the map in the view.
        # Default render (offset=0, zoom=1) centers (0,0) of SVG at center of screen?
        # No, offset is post_translate.

        # Let's simplify: svgelements allows iterating elements.
        # But we need to render images too.
        # Re-using render() is best.

        # To fit the whole map in (target_w, target_h):
        # We need scale_factor s = target_w / svg.width (assuming width fits).
        # And we need to center it.
        # But render() logic might clip if we are not careful.

        # Let's assume we render with default params into a buffer that matches SVG aspect ratio,
        # and we set scale_factor such that 1 SVG unit = X pixels.

        img = self.render(
            target_w,
            target_h,
            scale_factor=scale,
            offset_x=target_w / 2 - (self.svg.width * scale) / 2,  # Center X?
            offset_y=target_h / 2 - (self.svg.height * scale) / 2,  # Center Y?
            rotation=0,
            quality=1.0,
        )

        if img is None:
            return 0.0

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        def analyze_axis(axis_sum):
            # Autocorrelation
            n = len(axis_sum)
            # Normalize
            if np.max(axis_sum) == 0:
                return 0.0
            signal = axis_sum / np.max(axis_sum)

            # Correlate
            # We only care about lags up to half the image size
            lags = np.arange(10, n // 2)  # Ignore small lags (line thickness)
            corrs = []

            for lag in lags:
                # simple comparison: correlation coefficient or just dot product
                # We want periodicity.
                # c = mean( s[t] * s[t-lag] )
                c = np.sum(signal[lag:] * signal[:-lag])
                corrs.append(c)

            if not corrs:
                return 0.0

            # Find peaks
            corrs = np.array(corrs)
            # Find max peak
            peak_idx = np.argmax(corrs)
            best_lag = lags[peak_idx]

            # Confidence check: is it a sharp peak?
            return best_lag

        # Vertical grid lines (sum cols -> projection on X)
        col_sum = np.sum(edges, axis=0)
        px_spacing_x = analyze_axis(col_sum)

        # Horizontal grid lines (sum rows -> projection on Y)
        row_sum = np.sum(edges, axis=1)
        px_spacing_y = analyze_axis(row_sum)

        # Convert pixel spacing back to SVG units
        # spacing_svg = spacing_px / scale

        spacings = []
        if px_spacing_x > 0:
            spacings.append(px_spacing_x / scale)
        if px_spacing_y > 0:
            spacings.append(px_spacing_y / scale)

        if not spacings:
            return 0.0

        # Return average
        return sum(spacings) / len(spacings)

    def render(
        self,
        width: int,
        height: int,
        scale_factor: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        rotation: float = 0.0,
        quality: float = 1.0,
    ) -> np.ndarray:
        """
        Renders the SVG to a BGR numpy array with caching and dynamic quality.

        Args:
            width: Output width.
            height: Output height.
            scale_factor: Zoom level.
            offset_x: Pan X.
            offset_y: Pan Y.
            rotation: Rotation in degrees.
            quality: Render quality (0.1 to 1.0). Lower values render to a smaller buffer and upscale.
        """
        # Quantize float parameters to improve cache hit rate
        q_scale = round(scale_factor, 4)
        q_rot = round(rotation, 2)
        q_quality = round(max(0.1, min(1.0, quality)), 2)
        q_offset_x = int(round(offset_x))
        q_offset_y = int(round(offset_y))

        # Call cached internal renderer
        return self._render_internal(
            width, height, q_scale, q_offset_x, q_offset_y, q_rot, q_quality
        )

    @functools.lru_cache(maxsize=32)
    def _render_internal(
        self,
        target_width: int,
        target_height: int,
        scale_factor: float,
        offset_x: int,
        offset_y: int,
        rotation: float,
        quality: float,
    ) -> np.ndarray:
        """
        Internal cached renderer.
        """
        # Determine internal render resolution
        render_w = int(target_width * quality)
        render_h = int(target_height * quality)

        if render_w < 1 or render_h < 1:
            render_w = max(1, render_w)
            render_h = max(1, render_h)

        # Create blank black image
        image = np.zeros((render_h, render_w, 3), dtype=np.uint8)

        if self.svg is None:
            # If we just need to return black, we still need to upscale if quality < 1.0
            if quality < 1.0:
                return cv2.resize(
                    image, (target_width, target_height), interpolation=cv2.INTER_LINEAR
                )
            return image

        # Viewport Matrix Calculation
        # The viewport center is based on the target dimensions, but we are rendering to a scaled buffer.
        # However, the transformations (scale, translate) are relative to the original coordinate space.
        # If we render to a smaller buffer, we effectively zoom out everything by 'quality'.

        # We need the SVG to be rendered as if it were on the full size screen, then downsampled.
        # Or simpler: Scale the Viewport Matrix by 'quality'.

        cx, cy = target_width / 2, target_height / 2

        # Base Matrix: Matches the user's requested view
        vp_matrix = svgelements.Matrix()
        vp_matrix.post_scale(scale_factor, scale_factor)
        vp_matrix.post_rotate(math.radians(rotation), cx, cy)
        vp_matrix.post_translate(offset_x, offset_y)

        # Quality Scaling Matrix: Scales the entire view down to the render buffer size
        # We scale by 'quality', effectively fitting the full view into the smaller buffer.
        q_matrix = svgelements.Matrix()
        q_matrix.post_scale(quality, quality)

        # Combine: Apply user transform first, then scale down for buffer
        final_vp_matrix = vp_matrix * q_matrix

        # Iterate through SVG elements
        for element in self.svg.elements():
            try:
                # --- 1. Handle Raster Images ---
                if isinstance(element, svgelements.Image):
                    pil_img = element.image

                    # Try to load image if missing
                    if pil_img is None:
                        href = (
                            element.values.get("href")
                            or element.values.get("xlink:href")
                            or element.values.get("{http://www.w3.org/1999/xlink}href")
                        )
                        if href:
                            if href.startswith("data:image/"):
                                try:
                                    # Parse data URI: data:image/png;base64,.......
                                    header, data = href.split(",", 1)
                                    image_data = base64.b64decode(data)
                                    pil_img = Image.open(BytesIO(image_data))
                                except Exception:
                                    pass

                    if pil_img:
                        # Convert PIL to BGR
                        pil_img = pil_img.convert("RGB")
                        src_img = np.array(pil_img)
                        src_img = cv2.cvtColor(src_img, cv2.COLOR_RGB2BGR)

                        img_h, img_w = src_img.shape[:2]
                        target_w = element.width or img_w
                        target_h = element.height or img_h
                        target_x = element.x or 0
                        target_y = element.y or 0

                        # Local Matrix: Scale bitmap to target size, then translate
                        local_m = svgelements.Matrix()
                        local_m.post_scale(target_w / img_w, target_h / img_h)
                        local_m.post_translate(target_x, target_y)

                        # Apply element transform
                        if element.transform:
                            local_m = local_m * element.transform

                        # Apply Viewport
                        final_m = local_m * final_vp_matrix

                        # Extract Affine for OpenCV
                        M = np.float32(
                            [
                                [final_m.a, final_m.c, final_m.e],
                                [final_m.b, final_m.d, final_m.f],
                            ]
                        )

                        # Warp
                        warped = cv2.warpAffine(src_img, M, (render_w, render_h))

                        # Composite
                        mask = (warped > 0).any(axis=2).astype(np.uint8) * 255
                        image = cv2.bitwise_and(
                            image, image, mask=cv2.bitwise_not(mask)
                        )
                        image = cv2.add(image, warped)

                    continue

                # --- 2. Handle Text ---
                if isinstance(element, svgelements.Text):
                    # svgelements.Text has .text, .x, .y, .font_size, etc.
                    text_str = element.text
                    if not text_str:
                        continue

                    # Get position in SVG coordinates
                    # svgelements text position (x, y) is the baseline
                    tx = element.x or 0
                    ty = element.y or 0

                    # Apply Viewport Transform to the position
                    # We can use the final_vp_matrix to transform the point
                    p = final_vp_matrix.point_in_matrix_space((tx, ty))
                    render_x, render_y = int(p.x), int(p.y)

                    # Color
                    color = (255, 255, 255)  # Default white
                    if element.fill is not None and element.fill.value is not None:
                        c = element.fill
                        color = (c.blue, c.green, c.red)

                    # Font Scale
                    # OpenCV font scale is a multiplier.
                    # SVG font-size is in units.
                    # Approximate scale:
                    svg_font_size = element.font_size or 12
                    avg_scale = (abs(final_vp_matrix.a) + abs(final_vp_matrix.d)) / 2

                    # OpenCV Hershey fonts: scale 1.0 is roughly 20-30 pixels high.
                    # We want svg_font_size * avg_scale pixels high.
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
                    continue

                # --- 3. Handle Shapes (Paths, Rects, etc.) ---
                if isinstance(element, svgelements.Shape):
                    # Apply Viewport Transform
                    # We copy the path and apply matrix
                    path = svgelements.Path(element)
                    transformed_path = path * final_vp_matrix
                    transformed_path.reify()

                    closed_subpaths = []
                    open_subpaths = []
                    current_points = []
                    is_current_closed = False

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

                    for segment in transformed_path:
                        if isinstance(segment, svgelements.Move):
                            if current_points:
                                subpath_array = np.array(
                                    current_points, dtype=np.int32
                                ).reshape((-1, 1, 2))
                                if is_current_closed or element_naturally_closed:
                                    closed_subpaths.append(subpath_array)
                                else:
                                    open_subpaths.append(subpath_array)
                                current_points = []
                            is_current_closed = False
                            continue

                        if not current_points:
                            current_points.append(
                                (int(segment.start.x), int(segment.start.y))
                            )

                        if isinstance(segment, svgelements.Line):
                            current_points.append(
                                (int(segment.end.x), int(segment.end.y))
                            )
                        elif isinstance(segment, svgelements.Close):
                            is_current_closed = True
                        elif isinstance(
                            segment,
                            (
                                svgelements.QuadraticBezier,
                                svgelements.CubicBezier,
                                svgelements.Arc,
                            ),
                        ):
                            # Adaptive sampling could be better, but fixed is faster
                            for i in range(1, 11):  # 1 to 10
                                t = i / 10.0
                                p = segment.point(t)
                                current_points.append((int(p.x), int(p.y)))

                    if current_points:
                        subpath_array = np.array(
                            current_points, dtype=np.int32
                        ).reshape((-1, 1, 2))
                        if is_current_closed or element_naturally_closed:
                            closed_subpaths.append(subpath_array)
                        else:
                            open_subpaths.append(subpath_array)

                    all_subpaths = closed_subpaths + open_subpaths
                    if not all_subpaths:
                        continue

                    # Fill
                    if element.fill is not None and element.fill.value is not None:
                        c = element.fill
                        fill_color = (c.blue, c.green, c.red)
                        cv2.fillPoly(image, all_subpaths, fill_color)

                    # Stroke
                    if element.stroke is not None and element.stroke.value is not None:
                        c = element.stroke
                        color = (c.blue, c.green, c.red)
                        if sum(color) < 30:
                            color = (255, 255, 255)

                        thickness = 1
                        if element.stroke_width is not None:
                            # Scale stroke width by combined scale factor
                            # Approximate scale from matrix
                            avg_scale = (
                                abs(final_vp_matrix.a) + abs(final_vp_matrix.d)
                            ) / 2
                            thickness = max(1, int(element.stroke_width * avg_scale))

                        if closed_subpaths:
                            cv2.polylines(
                                image, closed_subpaths, True, color, thickness
                            )
                        if open_subpaths:
                            cv2.polylines(image, open_subpaths, False, color, thickness)

            except Exception:
                continue

        # If quality < 1.0, upscale to target size
        if quality < 1.0:
            return cv2.resize(
                image, (target_width, target_height), interpolation=cv2.INTER_LINEAR
            )

        return image

    def get_visibility_blockers(self) -> List[VisibilityBlocker]:
        """
        Extracts walls, doors, and windows from the SVG based on layer names.
        """
        if not self.svg:
            return []

        blockers = []

        def traverse(element, current_v_type=None, current_layer_name="", current_unbreakable=False):
            v_type = current_v_type
            layer_name = current_layer_name
            is_unbreakable = current_unbreakable

            # Check if this element defines a new visibility context (layer)
            if hasattr(element, "id") and element.id:
                id_lower = str(element.id).lower()
                if "wall" in id_lower:
                    v_type = VisibilityType.WALL
                    layer_name = str(element.id)
                elif "door" in id_lower:
                    v_type = VisibilityType.DOOR
                    layer_name = str(element.id)
                elif "window" in id_lower:
                    v_type = VisibilityType.WINDOW
                    layer_name = str(element.id)
                    if "unbreakable" in id_lower:
                        is_unbreakable = True

            # If it's a shape and we are in a visibility context, extract it
            if isinstance(element, svgelements.Shape) and v_type:
                # In svgelements, Path(element) creates a path and usually applies the element's transform.
                # However, for visibility, we want the absolute coordinates in the SVG.
                # element.transform should be the cumulative transform if the SVG was parsed.
                
                path = svgelements.Path(element)
                # To be absolutely sure we have global coordinates, we can reify the path
                # but Path(element) already includes element.transform.
                
                segments: List[Tuple[float, float]] = []
                for segment in path:
                    if isinstance(segment, svgelements.Move):
                        continue
                    if not segments:
                        segments.append((segment.start.x, segment.start.y))
                    
                    if isinstance(segment, svgelements.Line):
                        segments.append((segment.end.x, segment.end.y))
                    elif isinstance(segment, (svgelements.QuadraticBezier, svgelements.CubicBezier, svgelements.Arc)):
                        for i in range(1, 11):
                            p = segment.point(i / 10.0)
                            segments.append((p.x, p.y))
                    elif isinstance(segment, svgelements.Close):
                        # Close back to the first point of this subpath
                        if segments:
                            # We need to find the start of the current subpath.
                            # For simplicity, if we only have one subpath, it's segments[0].
                            # svgelements.Close has .start and .end too.
                            segments.append((segment.end.x, segment.end.y))

                if segments:
                    blockers.append(
                        VisibilityBlocker(
                            segments=segments,
                            type=v_type,
                            layer_name=layer_name,
                            is_unbreakable=is_unbreakable,
                        )
                    )

            # Recurse into children if it's a group or the root SVG
            if isinstance(element, (svgelements.Group, svgelements.SVG)):
                for child in element:
                    traverse(child, v_type, layer_name, is_unbreakable)

        traverse(self.svg)
        return blockers
