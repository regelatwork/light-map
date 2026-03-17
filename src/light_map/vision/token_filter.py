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

        for raw_token in detected_tokens:
            token = replace(raw_token)  # WORK ON A COPY
            # Masking check: filter out tokens outside map boundaries if provided
            if map_bounds is not None:
                min_x, min_y, max_x, max_y = map_bounds
                if not (
                    min_x <= token.world_x <= max_x and min_y <= token.world_y <= max_y
                ):
                    # If this token was previously tracked, purge it immediately
                    # as it is now in a "forbidden" zone.
                    if token.id in self.last_seen_tokens:
                        del self.last_seen_tokens[token.id]
                    if token.id in self.last_seen_times:
                        del self.last_seen_times[token.id]
                    continue

            new_seen_ids.add(token.id)

            # Smoothing
            if token.id in self.last_seen_tokens:
                last_token = self.last_seen_tokens[token.id]
                # Apply Alpha-Beta (simple Alpha here for now)
                token.world_x = (
                    last_token.world_x * (1.0 - self.alpha) + token.world_x * self.alpha
                )
                token.world_y = (
                    last_token.world_y * (1.0 - self.alpha) + token.world_y * self.alpha
                )

            self.last_seen_tokens[token.id] = token
            self.last_seen_times[token.id] = current_time

        # 2. Handle occlusion (keep lost tokens for a while)
        active_tokens = []
        ids_to_remove = []

        for token_id, last_time in self.last_seen_times.items():
            token = self.last_seen_tokens[token_id]
            elapsed = current_time - last_time

            if elapsed < self.occlusion_timeout_s:
                # Token is still "active"
                # If it's not in the new detections, it's occluded
                is_occluded = token_id not in new_seen_ids

                # Copy to avoid modifying state directly if needed
                from dataclasses import replace

                token_to_return = replace(token, is_occluded=is_occluded)

                # Populate name and color if available in config
                if token_configs and token_id in token_configs:
                    config = token_configs[token_id]
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
                ids_to_remove.append(token_id)

        # 3. Cleanup stale tokens
        for token_id in ids_to_remove:
            del self.last_seen_tokens[token_id]
            del self.last_seen_times[token_id]

        return active_tokens

    def _apply_grid_snapping(
        self,
        token: Token,
        grid_spacing: float,
        grid_origin_x: float,
        grid_origin_y: float,
        token_configs: Dict[int, Dict] = None,
    ) -> Token:
        if grid_spacing <= 0:
            return token

        # Get token size from config
        token_size = 1
        if token_configs and token.id in token_configs:
            token_size = token_configs[token.id].get("size", 1)

        # Snapping logic:
        # Odd Size: Center of grid cell.
        # Even Size: Intersection (corner) of grid cells.

        # Cell coordinate (fractional)
        grid_x_raw = (token.world_x - grid_origin_x) / grid_spacing
        grid_y_raw = (token.world_y - grid_origin_y) / grid_spacing

        if token_size % 2 == 1:
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

            snapped_grid_x = math.floor(grid_x_raw)
            snapped_grid_y = math.floor(grid_y_raw)

            token.world_x = grid_origin_x + (snapped_grid_x + 0.5) * grid_spacing
            token.world_y = grid_origin_y + (snapped_grid_y + 0.5) * grid_spacing
            token.grid_x = int(snapped_grid_x)
            token.grid_y = int(snapped_grid_y)

        else:
            # Even: round to nearest intersection (integer gx_raw)
            snapped_grid_x = round(grid_x_raw)
            snapped_grid_y = round(grid_y_raw)

            token.world_x = grid_origin_x + snapped_grid_x * grid_spacing
            token.world_y = grid_origin_y + snapped_grid_y * grid_spacing
            token.grid_x = int(snapped_grid_x)
            token.grid_y = int(snapped_grid_y)

        return token
