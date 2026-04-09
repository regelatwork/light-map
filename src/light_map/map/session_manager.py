import os
import datetime
import hashlib
import logging
from dataclasses import asdict
from typing import Optional
from light_map.core.common_types import SessionData, Token, ViewportState
from light_map.core.storage import StorageManager
from light_map.core.config_store import ConfigStore

_DEFAULT_STORAGE = StorageManager()
SESSION_DIR = os.path.join(_DEFAULT_STORAGE.get_data_dir(), "sessions")


class SessionManager:
    @staticmethod
    def _ensure_session_dir(session_dir: Optional[str] = None):
        target = session_dir or SESSION_DIR
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)

    @staticmethod
    def get_session_path(map_path: str, session_dir: Optional[str] = None) -> str:
        """Generates a unique session filename based on map path."""
        stem = os.path.splitext(os.path.basename(map_path))[0]
        # Use absolute path for stable hashing
        abs_path = os.path.abspath(map_path)
        path_hash = hashlib.md5(abs_path.encode()).hexdigest()[:8]
        filename = f"{stem}_{path_hash}.json"
        return os.path.join(session_dir or SESSION_DIR, filename)

    @staticmethod
    def has_session(map_path: str, session_dir: Optional[str] = None) -> bool:
        path = SessionManager.get_session_path(map_path, session_dir)
        return os.path.exists(path)

    @staticmethod
    def save_for_map(
        map_path: str, data: SessionData, session_dir: Optional[str] = None
    ) -> bool:
        SessionManager._ensure_session_dir(session_dir)
        path = SessionManager.get_session_path(map_path, session_dir)
        # Ensure data stores correct map file path
        data.map_file = map_path
        return SessionManager.save_session(path, data)

    @staticmethod
    def load_for_map(
        map_path: str, session_dir: Optional[str] = None
    ) -> Optional[SessionData]:
        path = SessionManager.get_session_path(map_path, session_dir)
        return SessionManager.load_session(path)

    @staticmethod
    def save_session(filepath: str, data: SessionData) -> bool:
        try:
            # Set timestamp if empty
            if not data.timestamp:
                data.timestamp = datetime.datetime.now().isoformat()

            # Serialize
            data_dict = asdict(data)

            store = ConfigStore(filepath)
            success = store.save(data_dict)
            if success:
                logging.info("Session saved to %s", filepath)
            return success
        except Exception as e:
            logging.error("Error saving session: %s", e)
            return False

    @staticmethod
    def load_session(filepath: str) -> Optional[SessionData]:
        store = ConfigStore(filepath)
        raw = store.load(dict)

        if not raw:
            logging.info("Session file not found or empty: %s", filepath)
            return None

        try:
            # Deserialize Viewport
            vp_data = raw.get("viewport", {})
            viewport = ViewportState(
                x=vp_data.get("x", 0.0),
                y=vp_data.get("y", 0.0),
                zoom=vp_data.get("zoom", 1.0),
                rotation=vp_data.get("rotation", 0.0),
            )

            # Deserialize Tokens
            tokens = []
            for t_data in raw.get("tokens", []):
                tokens.append(
                    Token(
                        id=t_data.get("id", 0),
                        world_x=t_data.get("world_x", 0.0),
                        world_y=t_data.get("world_y", 0.0),
                        grid_x=t_data.get("grid_x"),
                        grid_y=t_data.get("grid_y"),
                        confidence=t_data.get("confidence", 1.0),
                    )
                )

            return SessionData(
                map_file=raw.get("map_file", ""),
                viewport=viewport,
                tokens=tokens,
                door_states=raw.get("door_states", {}),
                timestamp=raw.get("timestamp", ""),
            )

        except Exception as e:
            logging.error("Error loading session: %s", e)
            return None
