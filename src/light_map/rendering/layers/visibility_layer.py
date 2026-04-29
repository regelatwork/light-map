
from light_map.core.common_types import ImagePatch, LayerMode
from light_map.core.constants import (
    ALPHA_OPAQUE,
)
from light_map.rendering.layers.visibility_base_layer import VisibilityBaseLayer


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

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        if (
            self.state is None
            or self.state.fow_disabled
            or self.state.visibility_mask is None
        ):
            return []

        return self._render_mask_to_patches(self.state.visibility_mask)


class ExclusiveVisionLayer(VisibilityBaseLayer):
    """
    Renders the real-time Line-of-Sight (LOS) for a single inspected token.
    Acting as a 'searchlight': it masks everything outside the vision mask with darkness.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layer_mode = LayerMode.MASKED

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # Pull version directly from WorldState atoms
        return max(
            self.state.inspected_token_mask_version,
            self.state.grid_metadata_version,
            self.state.viewport_version,
        )

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        if self.state is None or self.state.inspected_token_mask is None:
            return []

        # Uses ALPHA_OPAQUE (255) for shroud to create total darkness
        # Uses ALPHA_OPAQUE for background_alpha to fill area outside warped mask
        return self._render_mask_to_patches(
            self.state.inspected_token_mask,
            shroud_alpha=ALPHA_OPAQUE,
            background_alpha=ALPHA_OPAQUE,
        )
