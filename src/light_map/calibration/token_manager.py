"""
Module for managing and filtering calibration tokens from tokens.json.
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Token:
    id: str
    name: str
    type: str
    profile: str
    size: Optional[int]
    height_mm: Optional[float]
    color: Optional[str]

class TokenManager:
    def __init__(self, tokens_path: str):
        self.tokens_path = Path(tokens_path)
        self.token_profiles: Dict[str, Dict] = {}
        self.all_tokens: Dict[str, Token] = {}
        self._load_data()

    def _load_data(self):
        with open(self.tokens_path, "r") as f:
            data = json.load(f)
        
        self.token_profiles = data.get("token_profiles", {})
        raw_tokens = data.get("aruco_defaults", {})
        
        for tid, tdata in raw_tokens.items():
            # Resolve height if it's null but profile exists
            height = tdata.get("height_mm")
            if height is None and tdata.get("profile") in self.token_profiles:
                height = self.token_profiles[tdata["profile"]].get("height_mm")
            
            self.all_tokens[tid] = Token(
                id=tid,
                name=tdata.get("name", ""),
                type=tdata.get("type", ""),
                profile=tdata.get("profile", ""),
                size=tdata.get("size"),
                height_mm=height,
                color=tdata.get("color")
            )

    def get_candidate_tokens(self, id_range: range) -> List[Token]:
        """
        Returns a list of tokens within the specified ID range that have 
        a resolved, positive height.
        """
        candidates = []
        for tid in id_range:
            token_str = str(tid)
            if token_str in self.all_tokens:
                token = self.all_tokens[token_str]
                if token.height_mm is not None and token.height_mm > 0:
                    candidates.append(token)
        return candidates

    def get_token_by_id(self, tid: str) -> Optional[Token]:
        return self.all_tokens.get(tid)
