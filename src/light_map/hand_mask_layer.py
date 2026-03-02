from typing import List, Optional
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

    @property
    def is_dirty(self) -> bool:
        if not self.config.enable_hand_masking:
            return self._last_state_timestamp != -2
            
        if self.state is None:
            return True
            
        return self.state.hands_timestamp > self._last_state_timestamp

    def _generate_patches(self) -> List[ImagePatch]:
        if not self.config.enable_hand_masking:
            self._last_state_timestamp = -2
            return []
            
        if self.state is None:
            return []

        # Logic adapted from InteractiveApp._apply_hand_masking
        if not self.state.hands:
            # Still call compute_hulls with empty list for persistence if HandMasker uses it
            hulls = self.hand_masker.compute_hulls([], None)
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

            hulls = self.hand_masker.compute_hulls(self.state.hands, transform_pts)

        if not hulls:
            return []

        # Generate binary mask (white hands on black background)
        mask = self.hand_masker.generate_mask_image(
            hulls,
            self.config.width,
            self.config.height,
            padding=self.config.hand_mask_padding,
            blur=self.config.hand_mask_blur,
        )

        patch_data = np.zeros(
            (self.config.height, self.config.width, 4), dtype=np.uint8
        )
        patch_data[:, :, 3] = mask  # Alpha = mask intensity
        # RGB is already 0.

        patch = ImagePatch(
            x=0,
            y=0,
            width=self.config.width,
            height=self.config.height,
            data=patch_data,
        )

        return [patch]

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.hands_timestamp
