import math

from light_map.core.common_types import GridType, Token
from light_map.core.geometry import FlatTopHex, PointyTopHex


class TokenFilter:
    """
    Handles temporal filtering, occlusion buffering, and grid snapping for tokens.
    """

    def __init__(self, occlusion_timeout_ms: float = 2000.0, alpha: float = 0.3):
        self.occlusion_timeout_s = occlusion_timeout_ms / 1000.0
        self.alpha = alpha  # Smoothing factor for position
        self.last_seen_tokens: dict[int, Token] = {}
        self.last_seen_times: dict[int, float] = {}

    def update(
        self,
        detected_tokens: list[Token],
        current_time: float,
        grid_spacing: float = 0.0,
        grid_origin_x: float = 0.0,
        grid_origin_y: float = 0.0,
        token_configs: dict[int, dict] = None,
        map_bounds: tuple[float, float, float, float] | None = None,
        grid_type: GridType = GridType.SQUARE,
    ) -> list[Token]:
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
                    grid_type,
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
        token_configs: dict[int, dict] = None,
        grid_type: GridType = GridType.SQUARE,
    ) -> Token:
        if grid_spacing <= 0:
            return token

        if grid_type == GridType.SQUARE:
            return self._apply_square_snapping(
                token, grid_spacing, grid_origin_x, grid_origin_y, token_configs
            )
        else:
            return self._apply_hex_snapping(
                token,
                grid_spacing,
                grid_origin_x,
                grid_origin_y,
                token_configs,
                grid_type,
            )

    def _apply_square_snapping(
        self,
        token: Token,
        grid_spacing: float,
        grid_origin_x: float,
        grid_origin_y: float,
        token_configs: dict[int, dict] = None,
    ) -> Token:
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
            snapped_grid_x = math.floor(grid_x_raw)
            snapped_grid_y = math.floor(grid_y_raw)

            token.world_x = grid_origin_x + (snapped_grid_x + 0.5) * grid_spacing
            token.world_y = grid_origin_y + (snapped_grid_y + 0.5) * grid_spacing
            token.grid_x = int(snapped_grid_x)
            token.grid_y = int(snapped_grid_y)
        else:
            snapped_grid_x = round(grid_x_raw)
            snapped_grid_y = round(grid_y_raw)

            token.world_x = grid_origin_x + snapped_grid_x * grid_spacing
            token.world_y = grid_origin_y + snapped_grid_y * grid_spacing
            token.grid_x = int(snapped_grid_x)
            token.grid_y = int(snapped_grid_y)

        return token

    def _apply_hex_snapping(
        self,
        token: Token,
        grid_spacing: float,
        grid_origin_x: float,
        grid_origin_y: float,
        token_configs: dict[int, dict] = None,
        grid_type: GridType = GridType.HEX_POINTY,
    ) -> Token:
        hex_geo = (
            PointyTopHex(grid_spacing)
            if grid_type == GridType.HEX_POINTY
            else FlatTopHex(grid_spacing)
        )

        # 1. Transform world to hex-space
        rel_x = token.world_x - grid_origin_x
        rel_y = token.world_y - grid_origin_y
        q, r = hex_geo.from_pixel(rel_x, rel_y)

        # 2. Round to nearest hex center
        rq, rr = hex_geo.round(q, r)

        # 3. Transform back to world space
        snap_rel_x, snap_rel_y = hex_geo.to_pixel(rq, rr)
        token.world_x = grid_origin_x + snap_rel_x
        token.world_y = grid_origin_y + snap_rel_y
        token.grid_x = int(rq)
        token.grid_y = int(rr)

        return token
