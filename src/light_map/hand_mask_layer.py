from typing import List
import cv2
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch, AppConfig
from .core.world_state import WorldState
from .vision.hand_masker import HandMasker


class HandMaskLayer(Layer):
    """
    Renders black patches over hand regions to prevent projection on hands.
    Uses HandMasker and timestamps for caching.
    """

    def __init__(self, state: WorldState, config: AppConfig):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.config = config
        self.hand_masker = HandMasker()
        self._last_enabled = config.enable_hand_masking

    @property
    def is_dirty(self) -> bool:
        enabled_changed = self.config.enable_hand_masking != self._last_enabled
        if enabled_changed:
            return True

        if not self.config.enable_hand_masking:
            return False

        if self.state is None:
            return True

        # If we have active masks or are within the persistence window, we should be dirty
        # to ensure we eventually clear the mask.
        # Check if the masker is still persisting results
        if self.hand_masker.last_hulls:
            return True

        return self.state.hands_timestamp > self._last_state_timestamp

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        self._last_enabled = self.config.enable_hand_masking
        if not self.config.enable_hand_masking:
            return []

        if self.state is None:
            return []

        # Logic adapted from InteractiveApp._apply_hand_masking
        if not self.state.hands:
            # Still call compute_hulls with empty list for persistence if HandMasker uses it
            hulls = self.hand_masker.compute_hulls([], None, current_time)
        else:

            def transform_pts(pts):
                # pts is (N, 2) normalized camera coordinates
                cam_pts = pts.reshape(-1, 1, 2).copy()

                # We need the background shape to denormalize
                frame_h, frame_w = (1080, 1920)  # Defaults?
                if self.state.background is not None:
                    frame_h, frame_w = self.state.background.shape[:2]

                cam_pts[:, :, 0] *= frame_w
                cam_pts[:, :, 1] *= frame_h

                if self.config.distortion_model:
                    proj_pts = self.config.distortion_model.apply_correction(cam_pts)
                else:
                    proj_pts = cv2.perspectiveTransform(
                        cam_pts, self.config.projector_matrix
                    )
                return proj_pts.reshape(-1, 2)

            hulls = self.hand_masker.compute_hulls(
                self.state.hands, transform_pts, current_time
            )

        if not hulls:
            return []

        patches = []
        # Calculate padding in pixels for a 2cm (0.7874 inch) radius
        # This ensures the mask covers the entire hand, not just the skeleton points.
        padding_2cm = int(0.7874 * self.config.projector_ppi)

        for hull in hulls:
            # Get bounding box for this hull
            x, y, w, h = cv2.boundingRect(hull)

            # Apply padding to the bounding box
            pad = padding_2cm + 20  # extra margin for blur
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(self.config.width, x + w + pad)
            y2 = min(self.config.height, y + h + pad)

            pw, ph = x2 - x1, y2 - y1
            if pw <= 0 or ph <= 0:
                continue

            # Create local patch
            local_hull = hull - [x1, y1]

            # Draw hull mask on patch
            mask_patch = np.zeros((ph, pw), dtype=np.uint8)
            # Dilate the hull by drawing a thick boundary around it
            cv2.drawContours(
                mask_patch, [local_hull.astype(np.int32)], -1, 255, thickness=padding_2cm * 2
            )
            cv2.fillPoly(mask_patch, [local_hull.astype(np.int32)], 255)

            # Optional blur on the patch
            if self.config.hand_mask_blur > 1:
                k = self.config.hand_mask_blur * 2 + 1
                mask_patch = cv2.GaussianBlur(mask_patch, (k, k), 0)

            patch_data = np.zeros((ph, pw, 4), dtype=np.uint8)
            patch_data[:, :, 3] = mask_patch  # RGB is 0 (Black)

            patches.append(ImagePatch(x=x1, y=y1, width=pw, height=ph, data=patch_data))

        return patches

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.hands_timestamp
