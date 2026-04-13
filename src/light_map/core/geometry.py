import math
from typing import Tuple


class HexGeometry:
    """Base hex geometry logic."""
    def __init__(self, spacing: float):
        self.spacing = spacing
        # size is distance from center to vertex
        self.size = spacing / math.sqrt(3)

    def round(self, q: float, r: float) -> Tuple[int, int]:
        """Round fractional axial coordinates to nearest hex center."""
        x = q
        z = r
        y = -x - z

        rx, ry, rz = round(x), round(y), round(z)
        dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)

        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy > dz:
            ry = -rx - rz
        else:
            rz = -rx - ry

        return int(rx), int(rz)


class PointyTopHex(HexGeometry):
    """Pointy-top hex orientation logic."""
    def to_pixel(self, q: float, r: float) -> Tuple[float, float]:
        x = self.size * math.sqrt(3) * (q + r / 2.0)
        y = self.size * 1.5 * r
        return x, y

    def from_pixel(self, x: float, y: float) -> Tuple[float, float]:
        q = (math.sqrt(3) / 3 * x - 1 / 3 * y) / self.size
        r = (2 / 3 * y) / self.size
        return q, r


class FlatTopHex(HexGeometry):
    """Flat-top hex orientation logic."""
    def to_pixel(self, q: float, r: float) -> Tuple[float, float]:
        x = self.size * 1.5 * q
        y = self.size * math.sqrt(3) * (r + q / 2.0)
        return x, y

    def from_pixel(self, x: float, y: float) -> Tuple[float, float]:
        q = (2 / 3 * x) / self.size
        r = (-1 / 3 * x + math.sqrt(3) / 3 * y) / self.size
        return q, r
