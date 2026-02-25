import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """Handles application telemetry and usage statistics."""

    def __init__(self, storage_manager=None):
        self.storage_manager = storage_manager
        self.menu_stats: Dict[str, int] = {}
        self._load()

    def _get_stats_path(self) -> Optional[str]:
        if not self.storage_manager:
            return None
        return os.path.join(self.storage_manager.get_data_dir(), "menu_stats.json")

    def _load(self):
        path = self._get_stats_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.menu_stats = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load menu stats: {e}")

    def _save(self):
        path = self._get_stats_path()
        if path:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.menu_stats, f, indent=4)
            except Exception as e:
                logger.error(f"Failed to save menu stats: {e}")

    def log_menu_selection(self, action_id: str):
        """Records a menu selection."""
        self.menu_stats[action_id] = self.menu_stats.get(action_id, 0) + 1
        logger.info(
            f"Menu action selected: {action_id} (Total: {self.menu_stats[action_id]})"
        )
        self._save()
