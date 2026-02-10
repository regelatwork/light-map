import cv2
import numpy as np


class VisionEnhancer:
    def __init__(
        self, gamma: float = 0.5, clahe_clip: float = 2.0, clahe_grid: int = 8
    ):
        """
        Initializes the vision enhancement pipeline.

        Args:
            gamma: Gamma correction value.
                   < 1.0 (e.g. 0.5): Darkens image (recovers highlights).
                   > 1.0 (e.g. 1.5): Brightens image (recovers shadows).
            clahe_clip: Clip limit for CLAHE (Contrast Limiting). Higher = more contrast but more noise.
            clahe_grid: Grid size for CLAHE.
        """
        self.gamma = gamma
        self.clahe_grid = clahe_grid
        self.set_clahe_clip(clahe_clip)
        self._build_lut()

    def set_gamma(self, gamma: float):
        self.gamma = max(0.1, gamma)  # Prevent division by zero or negative
        self._build_lut()

    def set_clahe_clip(self, clip_limit: float):
        self.clahe_clip = max(0.1, clip_limit)
        self.clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip, tileGridSize=(self.clahe_grid, self.clahe_grid)
        )

    def _build_lut(self):
        """Pre-calculates the Gamma Lookup Table for performance."""
        # Gamma correction: V_out = V_in ^ (1/gamma)
        inv_gamma = 1.0 / self.gamma
        self.table = np.array(
            [((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]
        ).astype("uint8")

    def apply_gamma(self, image: np.ndarray) -> np.ndarray:
        """Applies gamma correction using LUT."""
        return cv2.LUT(image, self.table)

    def apply_clahe(self, image: np.ndarray) -> np.ndarray:
        """
        Applies CLAHE to the L-channel of a BGR/RGB image.
        """
        # Convert to LAB (L=Lightness, A=Green-Red, B=Blue-Yellow)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_chan, a, b = cv2.split(lab)

        # Apply CLAHE to L-channel
        l_enhanced = self.clahe.apply(l_chan)

        # Merge and convert back to BGR
        lab = cv2.merge((l_enhanced, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def process(self, image: np.ndarray) -> np.ndarray:
        """
        Runs the full enhancement pipeline.
        Input: BGR image.
        Output: BGR image (enhanced).
        """
        # 1. Gamma Correction
        enhanced = self.apply_gamma(image)

        # 2. CLAHE (Local Contrast)
        enhanced = self.apply_clahe(enhanced)

        return enhanced
