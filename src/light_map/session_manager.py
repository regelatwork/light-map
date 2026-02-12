import json
import os
import datetime
from dataclasses import asdict
from typing import Optional
from light_map.common_types import SessionData, Token, ViewportState


class SessionManager:
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
