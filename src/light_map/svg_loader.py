import svgelements
import numpy as np
import cv2
import math
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
                    if element.image:
                        # Convert PIL to BGR
                        pil_img = element.image.convert("RGB")
                        src_img = np.array(pil_img)
                        src_img = cv2.cvtColor(src_img, cv2.COLOR_RGB2BGR)

                        # Calculate Composite Matrix: Viewport * Element Transform
                        # Element transform puts image in SVG space. Viewport puts SVG in Screen space.
                        # Final = VP * E
                        # svgelements Matrix multiplication: A * B means A then B?
                        # transform = element.transform * vp_matrix?
                        # No, usually: Point' = VP * (E * Point) -> VP * E.

                        # Note: svgelements multiplication might be reverse of standard math notation depending on implementation.
                        # Assuming: (path * matrix) applies matrix AFTER path.
                        # So we want matrix = element.transform * vp_matrix ??
                        # Let's rely on vp_matrix being the "Parent" transform.
                        # But element.transform is local.

                        # Correct logic:
                        # 1. Image is at (0,0) with size (w,h) in its own local space?
                        #    No, svgelements.Image has x,y,width,height properties.
                        #    It effectively has a transform that places it there?
                        #    Or we must render it into the rect (x,y,w,h).

                        # Ideally, svgelements handles the rect via transform if we didn't use `element.image`.
                        # But `element.image` is the raw bitmap.

                        # Let's map the bitmap (0,0)->(w,h) to the target Screen Space.
                        # 1. Scale image to element.width/height?
                        # 2. Translate to element.x, element.y?
                        # 3. Apply element.transform?
                        # 4. Apply vp_matrix?

                        # Simplified:
                        # Construct a matrix that maps Bitmap Pixels -> Screen Pixels.

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
                            # Order check: M_total = M_local * M_element

                        # Apply Viewport
                        final_m = local_m * vp_matrix

                        # Extract Affine for OpenCV
                        # [[a, c, e], [b, d, f]]
                        M = np.float32(
                            [
                                [final_m.a, final_m.c, final_m.e],
                                [final_m.b, final_m.d, final_m.f],
                            ]
                        )

                        # Warp
                        warped = cv2.warpAffine(src_img, M, (width, height))

                        # Composite (Simple Max? Or Add? Or Alpha blend?)
                        # Assuming opaque for now or black background.
                        # Max allows layering without destroying previous content if black background.
                        # But warpAffine fills background with black (0).
                        # So simple addition works if no overlap?
                        # Let's use mask to overlay.

                        mask = (warped > 0).any(axis=2).astype(np.uint8) * 255
                        # Clear target area
                        image = cv2.bitwise_and(
                            image, image, mask=cv2.bitwise_not(mask)
                        )
                        # Add new
                        image = cv2.add(image, warped)

                    continue

                # --- 2. Handle Shapes (Paths, Rects, etc.) ---
                if isinstance(element, svgelements.Shape):
                    # Apply Viewport Transform
                    # We copy the path and apply matrix
                    path = svgelements.Path(element)
                    transformed_path = path * vp_matrix
                    transformed_path.reify()

                    points = []
                    for segment in transformed_path:
                        if isinstance(segment, (svgelements.Line, svgelements.Close)):
                            points.append((int(segment.start.x), int(segment.start.y)))
                            points.append((int(segment.end.x), int(segment.end.y)))
                        elif isinstance(
                            segment,
                            (
                                svgelements.QuadraticBezier,
                                svgelements.CubicBezier,
                                svgelements.Arc,
                            ),
                        ):
                            for i in range(11):
                                t = i / 10.0
                                p = segment.point(t)
                                points.append((int(p.x), int(p.y)))

                    if not points:
                        continue
                    pts_np = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

                    # Fill
                    if element.fill is not None and element.fill.value is not None:
                        c = element.fill
                        # Check alpha? svgelements usually handles opacity separate.
                        # Just RGB for now.
                        fill_color = (c.blue, c.green, c.red)
                        cv2.fillPoly(image, [pts_np], fill_color)

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
                        # Check if last point equals first? Or element property?
                        # svgelements path doesn't clearly expose 'closed' boolean easily on the iterator
                        # But Shape often has it.

                        cv2.polylines(image, [pts_np], is_closed, color, thickness)

            except Exception:
                continue

        return image
