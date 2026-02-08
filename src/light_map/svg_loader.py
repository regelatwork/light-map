import svgelements
import numpy as np
import cv2
import math


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

        Args:
            width: Output image width.
            height: Output image height.
            scale_factor: Zoom level.
            offset_x: X translation (pan).
            offset_y: Y translation (pan).
            rotation: Rotation in degrees (around screen center).

        Returns:
            np.ndarray: BGR image (uint8).
        """
        # Create blank black image
        image = np.zeros((height, width, 3), dtype=np.uint8)

        if self.svg is None:
            return image

        # Calculate Transform Matrix
        # We want to:
        # 1. Scale
        # 2. Rotate around screen center
        # 3. Translate (Pan)

        # Center of the screen
        cx, cy = width / 2, height / 2

        # Matrix multiplication order in svgelements is effectively:
        # New_Point = Matrix * Old_Point
        # Operations are applied in reverse order of definition usually?
        # Let's trust standard affine composition: T * R * S

        matrix = svgelements.Matrix()

        # 1. Scale relative to (0,0) of SVG
        matrix.post_scale(scale_factor, scale_factor)

        # 2. Rotate around screen center?
        # Typically rotation is around the map center or screen center.
        # Let's rotate around screen center (cx, cy).
        matrix.post_rotate(math.radians(rotation), cx, cy)

        # 3. Translate
        matrix.post_translate(offset_x, offset_y)

        # Iterate through SVG elements
        for element in self.svg.elements():
            if isinstance(
                element, svgelements.Shape
            ):  # Path, Rect, Circle, etc. inherit from Shape
                try:
                    # Apply transformation to a copy of the path
                    # Note: element itself might be a Path or Shape.
                    # We can convert to Path to unify handling.
                    path = svgelements.Path(element)

                    # Transform
                    transformed_path = path * matrix

                    # Apply transform to segments
                    transformed_path.reify()

                    # Convert to points for OpenCV
                    # svgelements paths are iterable segments
                    points = []

                    # Iterate segments and approximate
                    for segment in transformed_path:
                        # Simple linearization: Start point + End point
                        # For curves, we should subdivide.
                        # svgelements provides point(t)

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
                            # Subdivide curve into 10 linear segments
                            for i in range(11):
                                t = i / 10.0
                                p = segment.point(t)
                                points.append((int(p.x), int(p.y)))

                        elif isinstance(segment, svgelements.Move):
                            # Start a new polyline?
                            # For simplicity, we'll just treat it as a jump.
                            # OpenCV polylines takes a list of arrays.
                            # If we encounter a Move, we should split the points list.
                            pass

                    if not points:
                        continue

                    # Prepare for cv2.polylines (requires list of numpy arrays)
                    # We treat the whole path as one polyline for now, which connects segments.
                    # Ideally we'd split on 'Move'.
                    pts_np = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

                    # Determine Color (BGR)
                    color = (255, 255, 255)  # Default White
                    if element.stroke is not None and element.stroke.value is not None:
                        # svgelements Color has .red, .green, .blue properties
                        c = element.stroke
                        color = (c.blue, c.green, c.red)

                    # Determine Thickness
                    thickness = 1
                    if element.stroke_width is not None:
                        thickness = max(1, int(element.stroke_width * scale_factor))

                    cv2.polylines(image, [pts_np], False, color, thickness)

                except Exception:
                    continue

        return image
