import json
import logging
import os
from typing import Any, Dict
import numpy as np


class ConfigStore:
    """
    Centralized handler for loading and saving JSON configuration files.
    Provides robust atomic writes and type handling (like numpy serialization).
    """

    def __init__(self, filepath: str):
        self.filepath = filepath

    def load(self, default_factory=dict) -> Dict[str, Any]:
        """Loads JSON from file. Returns a default if file doesn't exist or is invalid."""
        if not os.path.exists(self.filepath):
            return default_factory()

        try:
            with open(self.filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Error loading config from %s: %s", self.filepath, e)
            return default_factory()

    def save(self, data: Dict[str, Any]) -> bool:
        """Saves data to JSON file with indentation and numpy type handling."""
        try:
            # Ensure directory exists
            dirname = os.path.dirname(self.filepath)
            if dirname:
                os.makedirs(dirname, exist_ok=True)

            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2, default=self._json_default)
            return True
        except Exception as e:
            logging.error("Error saving config to %s: %s", self.filepath, e)
            return False

    @staticmethod
    def _json_default(obj: Any) -> Any:
        """Handles numpy and other custom types for JSON serialization."""
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)
