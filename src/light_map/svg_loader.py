import svgelements
import numpy as np
import cv2
import math
import base64
from io import BytesIO
from PIL import Image


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

    def render(
        self,
        width: int,
        height: int,
        scale_factor: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        rotation: float = 0.0,
    ) -> np.ndarray:
        """
        Renders the SVG to a BGR numpy array.
        """
        # Create blank black image
        image = np.zeros((height, width, 3), dtype=np.uint8)

        if self.svg is None:
            return image

        # Viewport Matrix
        cx, cy = width / 2, height / 2

        vp_matrix = svgelements.Matrix()
        vp_matrix.post_scale(scale_factor, scale_factor)
        vp_matrix.post_rotate(math.radians(rotation), cx, cy)
        vp_matrix.post_translate(offset_x, offset_y)

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
                            else:
                                # External file? Not implemented for safety/path complexity
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
                        final_m = local_m * vp_matrix

                        # Extract Affine for OpenCV
                        M = np.float32(
                            [
                                [final_m.a, final_m.c, final_m.e],
                                [final_m.b, final_m.d, final_m.f],
                            ]
                        )

                        # Warp
                        warped = cv2.warpAffine(src_img, M, (width, height))

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
                    transformed_path = path * vp_matrix
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
                            # Move establishes a new current point, but doesn't add a drawn point itself
                            # The next segment will use this start point.
                            continue

                        # Ensure start point is added if starting new subpath
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
                            for i in range(1, 11):  # 1 to 10
                                t = i / 10.0
                                p = segment.point(t)
                                current_points.append((int(p.x), int(p.y)))

                    # Append final subpath
                    if current_points:
                        subpaths.append(
                            np.array(current_points, dtype=np.int32).reshape((-1, 1, 2))
                        )

                    if not subpaths:
                        continue

                    # Fill
                    if element.fill is not None and element.fill.value is not None:
                        c = element.fill
                        # Check alpha? svgelements usually handles opacity separate.
                        # Just RGB for now.
                        fill_color = (c.blue, c.green, c.red)
                        cv2.fillPoly(image, subpaths, fill_color)

                    # Stroke
                    if element.stroke is not None and element.stroke.value is not None:
                        c = element.stroke
                        color = (c.blue, c.green, c.red)
                        if sum(color) < 30:
                            color = (255, 255, 255)  # Invert Black

                        thickness = 1
                        if element.stroke_width is not None:
                            thickness = max(1, int(element.stroke_width * scale_factor))

                        # Determine if closed
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

                        # Draw all subpaths
                        cv2.polylines(image, subpaths, is_closed, color, thickness)

            except Exception:
                continue

        return image
