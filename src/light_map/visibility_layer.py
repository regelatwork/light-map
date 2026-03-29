import numpy as np
from typing import List, Optional
from .common_types import ImagePatch
from .constants import (
    ALPHA_OPAQUE,
)
from .visibility_base_layer import VisibilityBaseLayer


class VisibilityLayer(VisibilityBaseLayer):
    """
    Renders the current aggregated Line-of-Sight (LOS) for all PC tokens.
    Consumes mask from WorldState and transforms it to screen space.
    """

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(
            self.state.visibility_version,
            self.state.viewport_version,
            self.state.grid_metadata_version,
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None or self.state.visibility_mask is None:
            return []

        return self._render_mask_to_patches(self.state.visibility_mask)


class ExclusiveVisionLayer(VisibilityBaseLayer):
    """
    Renders the real-time Line-of-Sight (LOS) for a single inspected token.
    Acting as a 'searchlight': it masks everything outside the vision mask with darkness.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mask_override: Optional[np.ndarray] = None
    def set_mask(self, mask: Optional[np.ndarray]):
        self.mask_override = mask

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # If mask is overridden, we just render whenever the underlying mask is updated.
        # But wait, mask is passed manually here. We need to increment version if mask changes.
        # But the mask_override is set by someone else. We'll use system_time_version for now
        # if there's a mask override to ensure it renders, or we could add an internal version.
        if self.mask_override is not None:
            return self.state.system_time_version
        return max(
            self.state.visibility_version,
            self.state.grid_metadata_version,
            self.state.viewport_version,
        )
    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.mask_override is None:
            return []

        # Uses ALPHA_OPAQUE (255) for shroud to create total darkness
        # Uses ALPHA_OPAQUE for background_alpha to fill area outside warped mask
        return self._render_mask_to_patches(
            self.mask_override, shroud_alpha=ALPHA_OPAQUE, background_alpha=ALPHA_OPAQUE
        )
