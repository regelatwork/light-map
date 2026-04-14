import cv2
import numpy as np
from light_map.core.common_types import LayerMode, ImagePatch
from light_map.core.constants import ALPHA_OPAQUE


def composite_patch(
    buffer: np.ndarray,
    patch: ImagePatch,
    mode: LayerMode,
    screen_width: int,
    screen_height: int,
):
    """
    Blends a patch onto a buffer using optimized methods based on the layer mode.

    Args:
        buffer: The destination BGR/BGRA buffer (modified in-place).
        patch: The ImagePatch to composite.
        mode: The LayerMode to use.
        screen_width: Width of the screen buffer.
        screen_height: Height of the screen buffer.
    """
    # Bound checks
    buffer_x1, buffer_y1 = max(0, patch.x), max(0, patch.y)
    buffer_x2, buffer_y2 = (
        min(screen_width, patch.x + patch.width),
        min(screen_height, patch.y + patch.height),
    )

    if buffer_x1 >= buffer_x2 or buffer_y1 >= buffer_y2:
        return

    # Slice patch data if it's partially off-screen
    patch_x1, patch_y1 = buffer_x1 - patch.x, buffer_y1 - patch.y
    patch_x2, patch_y2 = (
        patch_x1 + (buffer_x2 - buffer_x1),
        patch_y1 + (buffer_y2 - buffer_y1),
    )
    patch_slice = patch.data[patch_y1:patch_y2, patch_x1:patch_x2]

    if mode == LayerMode.BLOCKING:
        # Fast slice assignment (ignore alpha)
        buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3] = patch_slice[:, :, :3]
        if buffer.shape[2] == 4:
            buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3] = ALPHA_OPAQUE

    elif mode == LayerMode.MASKED:
        # Boolean indexing fast-path using the alpha channel for binary masks
        if patch_slice.shape[2] == 4:
            alpha_channel = patch_slice[:, :, 3]
            mask = alpha_channel > 0
            if np.any(mask):
                # Use a view for the target region
                roi = buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2]
                roi[mask, :3] = patch_slice[mask, :3]
                if buffer.shape[2] == 4:
                    roi[mask, 3] = alpha_channel[mask]
        else:
            # If no alpha, treat as blocking
            buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3] = patch_slice[:, :, :3]
            if buffer.shape[2] == 4:
                buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3] = ALPHA_OPAQUE

    else:  # LayerMode.NORMAL
        if patch_slice.shape[2] == 4:
            alpha_channel = patch_slice[:, :, 3]
            if not np.any(alpha_channel):
                return

            # OPTIMIZATION: cv2.addWeighted if uniform alpha
            # This is significantly faster than manual blending.
            first_alpha = alpha_channel[0, 0]
            if np.all(alpha_channel == first_alpha):
                alpha_f = float(first_alpha) / 255.0
                if alpha_f == 1.0:
                    # Treat as blocking if fully opaque
                    buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3] = patch_slice[
                        :, :, :3
                    ]
                    if buffer.shape[2] == 4:
                        buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3] = (
                            ALPHA_OPAQUE
                        )
                    return
                elif alpha_f == 0.0:
                    return

                dst_view = buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3]
                src_bgr = np.ascontiguousarray(patch_slice[:, :, :3])
                
                if dst_view.flags.c_contiguous:
                    cv2.addWeighted(
                        src_bgr,
                        alpha_f,
                        dst_view,
                        1.0 - alpha_f,
                        0,
                        dst_view,
                    )
                else:
                    # Fallback for non-contiguous dst: blend into temporary contiguous array
                    tmp_dst = cv2.addWeighted(
                        src_bgr,
                        alpha_f,
                        np.ascontiguousarray(dst_view),
                        1.0 - alpha_f,
                        0,
                    )
                    buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3] = tmp_dst
                if buffer.shape[2] == 4:
                    # Composite alpha (simplified blend)
                    dst_alpha = buffer[
                        buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3
                    ].astype(np.uint16)
                    src_alpha = alpha_channel.astype(np.uint16)
                    blended_alpha = (
                        src_alpha
                        + dst_alpha * (ALPHA_OPAQUE - src_alpha) // ALPHA_OPAQUE
                    )
                    buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3] = (
                        blended_alpha.astype(np.uint8)
                    )
                return

            # Standard alpha blending for variable alpha
            alpha = alpha_channel[:, :, np.newaxis].astype(np.uint16)
            dst_view = buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3]
            roi = dst_view.astype(np.uint16)
            patch_bgr = patch_slice[:, :, :3].astype(np.uint16)

            blended = (patch_bgr * alpha + roi * (ALPHA_OPAQUE - alpha)) // ALPHA_OPAQUE
            dst_view[:] = blended.astype(np.uint8)

            if buffer.shape[2] == 4:
                dst_alpha = buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3].astype(
                    np.uint16
                )
                blended_alpha = (
                    alpha_channel.astype(np.uint16)
                    + dst_alpha
                    * (ALPHA_OPAQUE - alpha_channel.astype(np.uint16))
                    // ALPHA_OPAQUE
                )
                buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3] = (
                    blended_alpha.astype(np.uint8)
                )
        else:
            # No alpha channel, treat as blocking
            buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, :3] = patch_slice[:, :, :3]
            if buffer.shape[2] == 4:
                buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2, 3] = ALPHA_OPAQUE
