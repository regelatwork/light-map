import json
import logging
import os
import time
from typing import Dict, Optional, Any
from collections import deque
from contextlib import contextmanager
import numpy as np

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
    """Tracks glass-to-glass latency and high-level pipeline hops for performance monitoring."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.history: Dict[str, deque] = {}

        # Backward compatibility maps
        self.captures: Dict[int, int] = {}  # ts_capture -> ts_recorded
        self.detections: Dict[int, int] = {}  # ts_capture -> ts_detected

    def record_interval(self, name: str, duration_ns: int):
        """Records an arbitrary timing interval in nanoseconds."""
        if name not in self.history:
            self.history[name] = deque(maxlen=self.window_size)
        self.history[name].append(duration_ns)

    def record_capture(self, ts_capture: int):
        """Backward compatibility for recording frame capture."""
        # Note: ts_capture is expected to be in nanoseconds (time.perf_counter_ns())
        self.captures[ts_capture] = time.perf_counter_ns()
        if len(self.captures) > self.window_size * 2:
            oldest = sorted(self.captures.keys())[0]
            del self.captures[oldest]

    def record_detection(self, ts_capture: int, ts_detected: Optional[int] = None):
        """Backward compatibility for recording detection."""
        if ts_detected is None:
            ts_detected = time.perf_counter_ns()
        self.detections[ts_capture] = ts_detected

    def record_render(self, ts_capture: int, ts_rendered: Optional[int] = None):
        """Backward compatibility for recording render and calculating intervals."""
        if ts_rendered is None:
            ts_rendered = time.perf_counter_ns()

        if ts_capture in self.captures:
            baseline = ts_capture
            detect_time = self.detections.get(ts_capture, ts_rendered)

            self.record_interval("capture_to_detect", detect_time - baseline)
            self.record_interval("detect_to_render", ts_rendered - detect_time)
            self.record_interval("total_latency", ts_rendered - baseline)

    def get_report(self) -> Dict[str, Any]:
        """Returns statistical report for all tracked intervals."""
        report = {}
        for name, samples in self.history.items():
            if not samples or len(samples) == 0:
                continue

            arr = np.array(list(samples)) / 1_000_000.0  # Convert to milliseconds
            if arr.size == 0:
                continue
            report[name] = {
                "mean_ms": float(np.mean(arr)),
                "p50_ms": float(np.percentile(arr, 50)),
                "p90_ms": float(np.percentile(arr, 90)),
                "p95_ms": float(np.percentile(arr, 95)),
                "samples": len(samples),
            }

        # Backward compatibility for flat avg_* keys
        if "total_latency" in report:
            report["avg_total_latency_ms"] = report["total_latency"]["mean_ms"]
        if "capture_to_detect" in report:
            report["avg_detection_lag_ms"] = report["capture_to_detect"]["mean_ms"]
        if "detect_to_render" in report:
            report["avg_render_lag_ms"] = report["detect_to_render"]["mean_ms"]

        return report


@contextmanager
def track_wait(name: str, instrument: Optional[LatencyInstrument] = None):
    """Context manager to measure and record duration of an operation."""
    start_ns = time.perf_counter_ns()
    try:
        yield
    finally:
        duration_ns = time.perf_counter_ns() - start_ns
        if instrument:
            instrument.record_interval(name, duration_ns)
