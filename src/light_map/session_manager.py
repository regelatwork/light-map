import json
import os
import datetime
import hashlib
from dataclasses import asdict
from typing import Optional
from light_map.common_types import SessionData, Token, ViewportState

SESSION_DIR = "sessions"

class SessionManager:
    @staticmethod
    def _ensure_session_dir():
        if not os.path.exists(SESSION_DIR):
            os.makedirs(SESSION_DIR)

    @staticmethod
    def get_session_path(map_path: str) -> str:
        """Generates a unique session filename based on map path."""
        stem = os.path.splitext(os.path.basename(map_path))[0]
        # Use absolute path for stable hashing
        abs_path = os.path.abspath(map_path)
        path_hash = hashlib.md5(abs_path.encode()).hexdigest()[:8]
        filename = f"{stem}_{path_hash}.json"
        return os.path.join(SESSION_DIR, filename)

    @staticmethod
    def has_session(map_path: str) -> bool:
        path = SessionManager.get_session_path(map_path)
        return os.path.exists(path)

    @staticmethod
    def save_for_map(map_path: str, data: SessionData) -> bool:
        SessionManager._ensure_session_dir()
        path = SessionManager.get_session_path(map_path)
        # Ensure data stores correct map file path
        data.map_file = map_path
        return SessionManager.save_session(path, data)

    @staticmethod
    def load_for_map(map_path: str) -> Optional[SessionData]:
        path = SessionManager.get_session_path(map_path)
        return SessionManager.load_session(path)

    @staticmethod
    def save_session(filepath: str, data: SessionData) -> bool:
        try:
            # Set timestamp if empty
            if not data.timestamp:
                data.timestamp = datetime.datetime.now().isoformat()
            
            # Serialize
            data_dict = asdict(data)
            
            with open(filepath, "w") as f:
                json.dump(data_dict, f, indent=2)
            
            print(f"Session saved to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    @staticmethod
    def load_session(filepath: str) -> Optional[SessionData]:
        if not os.path.exists(filepath):
            print(f"Session file not found: {filepath}")
            return None
        
        try:
            with open(filepath, "r") as f:
                raw = json.load(f)
            
            # Deserialize Viewport
            vp_data = raw.get("viewport", {})
            viewport = ViewportState(
                x=vp_data.get("x", 0.0),
                y=vp_data.get("y", 0.0),
                zoom=vp_data.get("zoom", 1.0),
                rotation=vp_data.get("rotation", 0.0)
            )
            
            # Deserialize Tokens
            tokens = []
            for t_data in raw.get("tokens", []):
                tokens.append(Token(
                    id=t_data.get("id", 0),
                    world_x=t_data.get("world_x", 0.0),
                    world_y=t_data.get("world_y", 0.0),
                    grid_x=t_data.get("grid_x"),
                    grid_y=t_data.get("grid_y"),
                    confidence=t_data.get("confidence", 1.0)
                ))
            
            return SessionData(
                map_file=raw.get("map_file", ""),
                viewport=viewport,
                tokens=tokens,
                timestamp=raw.get("timestamp", "")
            )
            
        except Exception as e:
            print(f"Error loading session: {e}")
            return None
