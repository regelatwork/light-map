from typing import List
from light_map.core.common_types import Token, ResultType, DetectionResult, TokenMergePolicy


class TokenMergeManager:
    """
    Handles merging of tokens from multiple sources (Physical, Remote)
    based on configurable policies.
    """

    def __init__(self, policy: TokenMergePolicy = TokenMergePolicy.PHYSICAL_PRIORITY):
        self.policy = policy
        self._physical_tokens: List[Token] = []
        self._remote_tokens: List[Token] = []
        self._physical_raw_tokens: List[Token] = []
        self._remote_raw_tokens: List[Token] = []

    def set_policy(self, policy: TokenMergePolicy):
        """Updates the current merging policy."""
        self.policy = policy

    def update_source(self, result: DetectionResult) -> bool:
        """
        Updates the internal state for a specific source.
        Returns True if the source state actually changed.
        """
        if result.type != ResultType.ARUCO or "tokens" not in result.data:
            return False

        source = result.metadata.get("source", "physical")
        new_tokens = result.data["tokens"]
        new_raw_tokens = result.data.get("raw_tokens", [])

        changed = False
        if source == "remote":
            if not self._tokens_equal(
                self._remote_tokens, new_tokens
            ) or not self._tokens_equal(self._remote_raw_tokens, new_raw_tokens):
                self._remote_tokens = new_tokens
                self._remote_raw_tokens = new_raw_tokens
                changed = True
        else:
            if not self._tokens_equal(
                self._physical_tokens, new_tokens
            ) or not self._tokens_equal(self._physical_raw_tokens, new_raw_tokens):
                self._physical_tokens = new_tokens
                self._physical_raw_tokens = new_raw_tokens
                changed = True

        return changed

    def get_merged_tokens(self) -> List[Token]:
        """
        Merges tokens based on the current policy.
        """
        if self.policy == TokenMergePolicy.PHYSICAL_ONLY:
            return self._physical_tokens
        if self.policy == TokenMergePolicy.REMOTE_ONLY:
            return self._remote_tokens

        merged = {}
        if self.policy == TokenMergePolicy.PHYSICAL_PRIORITY:
            # Remote tokens first, physical wins conflicts
            for t in self._remote_tokens:
                merged[t.id] = t
            for t in self._physical_tokens:
                merged[t.id] = t
        elif self.policy == TokenMergePolicy.REMOTE_PRIORITY:
            # Physical tokens first, remote wins conflicts
            for t in self._physical_tokens:
                merged[t.id] = t
            for t in self._remote_tokens:
                merged[t.id] = t

        return list(merged.values())

    def get_merged_raw_tokens(self) -> List[Token]:
        """
        Merges raw tokens based on the current policy.
        """
        if self.policy == TokenMergePolicy.PHYSICAL_ONLY:
            return self._physical_raw_tokens
        if self.policy == TokenMergePolicy.REMOTE_ONLY:
            return self._remote_raw_tokens

        merged = {}
        if self.policy == TokenMergePolicy.PHYSICAL_PRIORITY:
            for t in self._remote_raw_tokens:
                merged[t.id] = t
            for t in self._physical_raw_tokens:
                merged[t.id] = t
        elif self.policy == TokenMergePolicy.REMOTE_PRIORITY:
            for t in self._physical_raw_tokens:
                merged[t.id] = t
            for t in self._remote_raw_tokens:
                merged[t.id] = t

        return list(merged.values())

    def _tokens_equal(self, list1: List[Token], list2: List[Token]) -> bool:
        """
        Compares two token lists for semantic equality (positions and status).
        """
        if len(list1) != len(list2):
            return False

        # Sort by ID for deterministic comparison
        s1 = sorted(list1, key=lambda t: t.id)
        s2 = sorted(list2, key=lambda t: t.id)

        for t1, t2 in zip(s1, s2):
            if t1.id != t2.id:
                return False

            # Use Grid Snapping if available (Stable against noise)
            if t1.grid_x is not None and t2.grid_x is not None:
                if t1.grid_x != t2.grid_x or t1.grid_y != t2.grid_y:
                    return False
            else:
                if (
                    abs(t1.world_x - t2.world_x) > 1.0
                    or abs(t1.world_y - t2.world_y) > 1.0
                ):
                    return False

            # Check status flags
            if t1.is_occluded != t2.is_occluded or t1.is_duplicate != t2.is_duplicate:
                return False

        return True
