import json
import logging
import os
import time
from typing import Dict, Optional, List

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


class LatencyInstrument:
    """Tracks glass-to-glass latency for performance monitoring."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.captures: Dict[int, int] = {}  # ts_capture -> ts_recorded
        self.detections: Dict[int, int] = {}  # ts_capture -> ts_detected
        self.renders: Dict[int, int] = {}  # ts_capture -> ts_rendered

        self.history: List[Dict[str, float]] = []

    def record_capture(self, ts_capture: int):
        self.captures[ts_capture] = int(time.perf_counter() * 1e6)
        # Prune old
        if len(self.captures) > self.window_size * 2:
            oldest = sorted(self.captures.keys())[0]
            del self.captures[oldest]

    def record_detection(self, ts_capture: int, ts_detected: Optional[int] = None):
        if ts_detected is None:
            ts_detected = int(time.perf_counter() * 1e6)
        self.detections[ts_capture] = ts_detected

    def record_render(self, ts_capture: int, ts_rendered: Optional[int] = None):
        if ts_rendered is None:
            ts_rendered = int(time.perf_counter() * 1e6)
        self.renders[ts_capture] = ts_rendered

        # Calculate and store in history
        if ts_capture in self.captures:
            # Use provided ts_capture as baseline if possible
            baseline = ts_capture
            detect_time = self.detections.get(ts_capture, ts_rendered)

            detect_lag = (detect_time - baseline) / 1000.0
            render_lag = (ts_rendered - detect_time) / 1000.0
            total = (ts_rendered - baseline) / 1000.0

            self.history.append(
                {"detect": detect_lag, "render": render_lag, "total": total}
            )

            if len(self.history) > self.window_size:
                self.history.pop(0)

    def get_report(self) -> Dict[str, float]:
        if not self.history:
            return {
                "avg_total_latency_ms": 0.0,
                "avg_detection_lag_ms": 0.0,
                "avg_render_lag_ms": 0.0,
            }

        return {
            "avg_total_latency_ms": sum(h["total"] for h in self.history)
            / len(self.history),
            "avg_detection_lag_ms": sum(h["detect"] for h in self.history)
            / len(self.history),
            "avg_render_lag_ms": sum(h["render"] for h in self.history)
            / len(self.history),
        }
