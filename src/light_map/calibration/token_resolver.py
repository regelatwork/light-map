"""
Module for resolving token metadata from tokens.json, specifically for calibration.
"""

import json
import logging


logger = logging.getLogger(__name__)


class TokenResolver:
    def __init__(self, tokens_json_path: str):
        self.tokens_json_path = tokens_json_path
        self.token_profiles = {}
        self.aruco_defaults = {}
        self.load_tokens()

    def load_tokens(self):
        try:
            with open(self.tokens_json_path) as f:
                data = json.load(f)
                self.token_profiles = data.get("token_profiles", {})
                self.aruco_defaults = data.get("aruco_defaults", {})
        except Exception as e:
            logger.error("Failed to load tokens.json from %s: %s", self.tokens_json_path, e)

    def resolve_height(self, token_id: str) -> float | None:
        """
        Resolves the physical height of a token ID.
        """
        # Check if it's in aruco_defaults
        if token_id in self.aruco_defaults:
            entry = self.aruco_defaults[token_id]
            # If height is explicitly set, return it
            height_mm = entry.get("height_mm")
            if height_mm is not None:
                return float(height_mm)

            # Otherwise, resolve via profile
            profile_name = entry.get("profile")
            if profile_name and profile_name in self.token_profiles:
                return float(self.token_profiles[profile_name].get("height_mm", 0.0))

        # If it's not in aruco_defaults, maybe it's directly in token_profiles?
        # This depends on how tokens.json is structured.
        # Looking at the current tokens.json, it's only in aruco_defaults.

        return None

    def get_candidate_tokens(self) -> list[str]:
        """
        Returns a list of token IDs that have a positive height.
        """
        candidates = []
        for token_id in self.aruco_defaults.keys():
            try:
                t_id = int(token_id)
                if 0 <= t_id <= 39:
                    height = self.resolve_height(token_id)
                    if height is not None and height > 0:
                        candidates.append(token_id)
            except ValueError:
                continue
        return candidates

    def get_height_map(self) -> dict[int, float]:
        """
        Returns a mapping of user token IDs (0-39) to their resolved heights.
        """
        height_map = {}
        for token_id in self.aruco_defaults.keys():
            # Only include user tokens (0-39)
            try:
                t_id = int(token_id)
                if 0 <= t_id <= 39:
                    height = self.resolve_height(token_id)
                    if height is not None and height > 0:
                        height_map[t_id] = height
            except ValueError:
                continue
        return height_map

    def get_token_sizes(self) -> dict[int, float]:
        """
        Returns a mapping of user token IDs (0-39) to their resolved sizes.
        """
        size_map = {}
        for token_id in self.aruco_defaults.keys():
            try:
                t_id = int(token_id)
                if 0 <= t_id <= 39:
                    entry = self.aruco_defaults[token_id]
                    profile_name = entry.get("profile")
                    if profile_name and profile_name in self.token_profiles:
                        size_map[t_id] = float(self.token_profiles[profile_name].get("size", 1.0))
                    else:
                        size_map[t_id] = 1.0
            except ValueError:
                continue
        return size_map
