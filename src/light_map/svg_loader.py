import svgelements
import numpy as np
import cv2
import math
import base64
from io import BytesIO
from PIL import Image
import functools
from collections import Counter


class SVGLoader:
    def __init__(self, filename: str):
        """
        Initialize the SVG loader.

        Args:
            filename: Path to the .svg file.
        """
        self.filename = filename
        try:
            # Parse SVG with explicit unit scaling (defaulting to 96 DPI)
            self.svg = svgelements.SVG.parse(filename)
        except Exception as e:
            print(f"Error loading SVG: {e}")
            self.svg = None

    def detect_grid_spacing(self) -> float:
        """
        Analyzes the SVG geometry to find the most likely grid spacing.
        Returns the spacing in SVG units. Returns 0.0 if no grid detected.
        """
        if not self.svg:
            return 0.0

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
                if hasattr(element, 'x1'):
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
        def find_spacing(coords):
            if not coords:
                return 0.0
            
            # Round to nearest 0.1 to handle float errors
            sorted_coords = sorted([round(c, 1) for c in coords])
            unique_coords = sorted(list(set(sorted_coords)))
            
            if len(unique_coords) < 3:
                return 0.0
            
            # Calculate gaps
            gaps = []
            for i in range(len(unique_coords) - 1):
                gap = unique_coords[i+1] - unique_coords[i]
                if gap > 1.0: # Ignore tiny gaps
                    gaps.append(round(gap, 1))
            
            if not gaps:
                return 0.0
                
            # Find mode
            counts = Counter(gaps)
            most_common = counts.most_common(1)
            if not most_common:
                return 0.0
            
            mode_gap, count = most_common[0]
            
            # Heuristic: The mode must appear at least twice (3 lines)
            if count < 2:
                return 0.0
                
            return mode_gap

        # Collect coords from Rects properly
        # Rect(x, y, w, h) -> Vertical lines at x, x+w. Horizontal at y, y+h.
        
        spacing_x = find_spacing(x_coords)
        spacing_y = find_spacing(y_coords)
        
        # If both found, return average if close, otherwise X
        if spacing_x > 0 and spacing_y > 0:
            if abs(spacing_x - spacing_y) < 1.0:
                return (spacing_x + spacing_y) / 2
            return spacing_x # Prefer X or maybe specific logic
        
        return max(spacing_x, spacing_y)

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

        # Call cached internal renderer
        return self._render_internal(
            width, height, q_scale, offset_x, offset_y, q_rot, q_quality
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

                # --- 2. Handle Shapes (Paths, Rects, etc.) ---
                if isinstance(element, svgelements.Shape):
                    # Apply Viewport Transform
                    # We copy the path and apply matrix
                    path = svgelements.Path(element)
                    transformed_path = path * final_vp_matrix
                    transformed_path.reify()

                    subpaths = []
                    current_points = []

                    for segment in transformed_path:
                        if isinstance(segment, svgelements.Move):
                            if current_points:
                                subpaths.append(
                                    np.array(current_points, dtype=np.int32).reshape(
                                        (-1, 1, 2)
                                    )
                                )
                                current_points = []
                            continue

                        if not current_points:
                            current_points.append(
                                (int(segment.start.x), int(segment.start.y))
                            )

                        if isinstance(segment, (svgelements.Line, svgelements.Close)):
                            current_points.append(
                                (int(segment.end.x), int(segment.end.y))
                            )
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
                        subpaths.append(
                            np.array(current_points, dtype=np.int32).reshape((-1, 1, 2))
                        )

                    if not subpaths:
                        continue

                    # Fill
                    if element.fill is not None and element.fill.value is not None:
                        c = element.fill
                        fill_color = (c.blue, c.green, c.red)
                        cv2.fillPoly(image, subpaths, fill_color)

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

                        is_closed = False
                        if isinstance(
                            element,
                            (
                                svgelements.Rect,
                                svgelements.Circle,
                                svgelements.Ellipse,
                                svgelements.Polygon,
                            ),
                        ):
                            is_closed = True

                        cv2.polylines(image, subpaths, is_closed, color, thickness)

            except Exception:
                continue

        # If quality < 1.0, upscale to target size
        if quality < 1.0:
            return cv2.resize(
                image, (target_width, target_height), interpolation=cv2.INTER_LINEAR
            )

        return image
