import json
import logging
import os
import time
from typing import Dict, Optional, Any, List
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

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.history: Dict[str, List[int]] = {}
        self._last_report_time = time.perf_counter()

        # Backward compatibility maps
        self.captures: Dict[int, int] = {}  # ts_capture -> ts_recorded
        self.detections: Dict[int, int] = {}  # ts_capture -> ts_detected

    def record_interval(self, name: str, duration_ns: int):
        """Records an arbitrary timing interval in nanoseconds."""
        if name not in self.history:
            self.history[name] = []
        self.history[name].append(duration_ns)
        # Optional: still cap the list to avoid memory leaks if report is never called
        if len(self.history[name]) > self.window_size:
            self.history[name].pop(0)

    def record_capture(self, ts_capture: int):
        """Backward compatibility for recording frame capture."""
        # Note: ts_capture is expected to be in nanoseconds (time.perf_counter_ns())
        self.captures[ts_capture] = time.perf_counter_ns()
        if len(self.captures) > self.window_size:
            # Simple cleanup of old entries
            if len(self.captures) > 2000:
                keys = sorted(self.captures.keys())
                for k in keys[:1000]:
                    del self.captures[k]

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
            if not samples:
                continue

            arr = np.array(samples) / 1_000_000.0  # Convert to milliseconds
            if arr.size == 0:
                continue

            report[name] = {
                "avg_ms": float(np.mean(arr)),
                "p50_ms": float(np.percentile(arr, 50)) if arr.size > 0 else 0.0,
                "p90_ms": float(np.percentile(arr, 90)) if arr.size > 0 else 0.0,
                "p95_ms": float(np.percentile(arr, 95)) if arr.size > 0 else 0.0,
                "samples": len(samples),
            }

        return report

    def log_and_reset_if_needed(
        self, interval_s: float = 10.0, level: int = logging.DEBUG
    ):
        """Logs the current statistics and resets history if interval has passed."""
        now = time.perf_counter()
        if now - self._last_report_time >= interval_s:
            report = self.get_report()
            if report:
                msg = f"Performance Statistics (last {interval_s}s):\n"
                for label, stats in report.items():
                    msg += (
                        f"  {label:25}: avg={stats['avg_ms']:6.1f}ms, "
                        f"p50={stats['p50_ms']:6.1f}ms, p90={stats['p90_ms']:6.1f}ms, "
                        f"p95={stats['p95_ms']:6.1f}ms ({stats['samples']} samples)\n"
                    )
                logger.log(level, msg)

            # Reset
            self.history.clear()
            self._last_report_time = now


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
