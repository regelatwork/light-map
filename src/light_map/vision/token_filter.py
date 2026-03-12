import math
from typing import Dict, List, Optional, Tuple
from light_map.common_types import Token


class TokenFilter:
    """
    Handles temporal filtering, occlusion buffering, and grid snapping for tokens.
    """

    def __init__(self, occlusion_timeout_ms: float = 2000.0, alpha: float = 0.3):
        self.occlusion_timeout_s = occlusion_timeout_ms / 1000.0
        self.alpha = alpha  # Smoothing factor for position
        self.last_seen_tokens: Dict[int, Token] = {}
        self.last_seen_times: Dict[int, float] = {}

    def update(
        self,
        detected_tokens: List[Token],
        current_time: float,
        grid_spacing: float = 0.0,
        grid_origin_x: float = 0.0,
        grid_origin_y: float = 0.0,
        token_configs: Dict[int, Dict] = None,
        map_bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[Token]:
        """
        Updates the filter with new detections and returns the filtered tokens.

        Args:
            detected_tokens: Raw detections from the current frame.
            current_time: Current timestamp in seconds.
            grid_spacing: Spacing for grid snapping.
            grid_origin_x: Origin X for grid snapping.
            grid_origin_y: Origin Y for grid snapping.
            token_configs: Optional dictionary mapping token IDs to their configurations.
            map_bounds: Optional (min_x, min_y, max_x, max_y) in world coordinates.
                       Tokens outside these bounds will be ignored.
        """
        new_seen_ids = set()

        # 1. Process new detections
        from dataclasses import replace

        for raw_dt in detected_tokens:
            dt = replace(raw_dt)  # WORK ON A COPY
            # Masking check: filter out tokens outside map boundaries if provided
            if map_bounds is not None:
                min_x, min_y, max_x, max_y = map_bounds
                if not (min_x <= dt.world_x <= max_x and min_y <= dt.world_y <= max_y):
                    # If this token was previously tracked, purge it immediately
                    # as it is now in a "forbidden" zone.
                    if dt.id in self.last_seen_tokens:
                        del self.last_seen_tokens[dt.id]
                    if dt.id in self.last_seen_times:
                        del self.last_seen_times[dt.id]
                    continue

            new_seen_ids.add(dt.id)

            # Smoothing
            if dt.id in self.last_seen_tokens:
                lt = self.last_seen_tokens[dt.id]
                # Apply Alpha-Beta (simple Alpha here for now)
                dt.world_x = lt.world_x * (1.0 - self.alpha) + dt.world_x * self.alpha
                dt.world_y = lt.world_y * (1.0 - self.alpha) + dt.world_y * self.alpha

            self.last_seen_tokens[dt.id] = dt
            self.last_seen_times[dt.id] = current_time

        # 2. Handle occlusion (keep lost tokens for a while)
        active_tokens = []
        ids_to_remove = []

        for tid, last_time in self.last_seen_times.items():
            dt = self.last_seen_tokens[tid]
            elapsed = current_time - last_time

            if elapsed < self.occlusion_timeout_s:
                # Token is still "active"
                # If it's not in the new detections, it's occluded
                is_occluded = tid not in new_seen_ids

                # Copy to avoid modifying state directly if needed
                from dataclasses import replace

                token_to_return = replace(dt, is_occluded=is_occluded)

                # Populate name and color if available in config
                if token_configs and tid in token_configs:
                    config = token_configs[tid]
                    token_to_return.name = config.get("name")
                    token_to_return.color = config.get("color")
                    token_to_return.type = config.get("type", "NPC")

                # Apply Grid Snapping if applicable
                final_token = self._apply_grid_snapping(
                    token_to_return,
                    grid_spacing,
                    grid_origin_x,
                    grid_origin_y,
                    token_configs,
                )

                active_tokens.append(final_token)
            else:
                ids_to_remove.append(tid)

        # 3. Cleanup stale tokens
        for tid in ids_to_remove:
            del self.last_seen_tokens[tid]
            del self.last_seen_times[tid]

        return active_tokens

    def _apply_grid_snapping(
        self,
        token: Token,
        spacing: float,
        ox: float,
        oy: float,
        token_configs: Dict[int, Dict] = None,
    ) -> Token:
        if spacing <= 0:
            return token

        # Get token size from config
        size = 1
        if token_configs and token.id in token_configs:
            size = token_configs[token.id].get("size", 1)

        # Snapping logic:
        # Odd Size: Center of grid cell.
        # Even Size: Intersection (corner) of grid cells.

        # Cell coordinate (fractional)
        gx_raw = (token.world_x - ox) / spacing
        gy_raw = (token.world_y - oy) / spacing

        if size % 2 == 1:
            # Odd: round to nearest integer (center is i + 0.5, but we use i for cell ID)
            # Actually if world_x = ox + (gx + 0.5) * spacing
            # Then gx = floor((world_x - ox) / spacing)
            # Wait, if we want to SNAP to the center of cell gx:
            # snapped_x = ox + (round(gx_raw - 0.5) + 0.5) * spacing? No.
            # snapped_x = ox + (floor(gx_raw) + 0.5) * spacing.

            # Offset for larger odd sizes (e.g. size 3 center is at cell gx+1)
            # If size=1, center is cell gx.
            # If size=3, center is cell gx. (occupies gx-1, gx, gx+1)
            # Wait, if centroid is at gx_raw.
            # Snapped centroid for size 1 should be floor(gx_raw) + 0.5.
            # Snapped centroid for size 3 should be floor(gx_raw) + 0.5.

            snapped_gx = math.floor(gx_raw)
            snapped_gy = math.floor(gy_raw)

            token.world_x = ox + (snapped_gx + 0.5) * spacing
            token.world_y = oy + (snapped_gy + 0.5) * spacing
            token.grid_x = int(snapped_gx)
            token.grid_y = int(snapped_gy)

        else:
            # Even: round to nearest intersection (integer gx_raw)
            snapped_gx = round(gx_raw)
            snapped_gy = round(gy_raw)

            token.world_x = ox + snapped_gx * spacing
            token.world_y = oy + snapped_gy * spacing
            token.grid_x = int(snapped_gx)
            token.grid_y = int(snapped_gy)

        return token
