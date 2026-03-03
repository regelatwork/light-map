import cv2
import time
import logging
from typing import Optional, List, Callable, Dict, Any
from light_map.core.world_state import WorldState
from light_map.core.temporal_event_manager import TemporalEventManager
from light_map.vision.process_manager import VisionProcessManager
from light_map.vision.frame_producer import FrameProducer
from light_map.input_manager import InputManager
from light_map.common_types import DetectionResult, Action, Token
from light_map.core.analytics import LatencyInstrument, track_wait


class MainLoopController:
    """
    Heart of the MainProcess. Aggregates results, updates state,
    and coordinates rendering.
    """

    def __init__(
        self,
        world_state: WorldState,
        process_manager: VisionProcessManager,
        input_manager: InputManager,
        frame_producer: Optional[FrameProducer] = None,
        target_fps: int = 60,
        aruco_mapper: Optional[Callable[[Dict[str, Any]], List[Token]]] = None,
        state_mirror: Optional[Dict[str, Any]] = None,
    ):
        self.state = world_state
        self.manager = process_manager
        self.input = input_manager
        self.producer = frame_producer
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self.aruco_mapper = aruco_mapper
        self.state_mirror = state_mirror

        self.is_running = False
        self.instrument = LatencyInstrument()
        self.events = TemporalEventManager()
        self.debug_mode = False
        self._last_report_time = 0.0

    def tick(self) -> List[Action]:
        """Performs one iteration of the main loop."""
        # 1. Update Background from SHM
        if self.producer:
            # Check for new frame
            ts = self.producer.get_latest_timestamp()
            if ts is not None and ts > self.state.last_frame_timestamp:
                self.instrument.record_capture(ts)

                with track_wait("shm_wait_main", self.instrument):
                    shm_view = self.producer.get_latest_frame()

                if shm_view is not None:
                    ts_shm_pushed = self.producer.get_shm_pushed_timestamp()
                    if ts_shm_pushed:
                        self.instrument.record_interval(
                            "capture_to_shm", ts_shm_pushed - ts
                        )
                        self.instrument.record_interval(
                            "shm_transit_to_main",
                            time.perf_counter_ns() - ts_shm_pushed,
                        )

                    self.state.update_from_frame(shm_view, ts)
                    self.producer.release()

        # 2. Drain Vision Results from Queues
        with track_wait("queue_wait_main", self.instrument):
            self._drain_queues()

        # 3. Map Raw ArUco if available
        if self.state.raw_aruco["ids"]:
            if self.aruco_mapper:
                mapped_result = self.aruco_mapper(self.state.raw_aruco)
                if isinstance(mapped_result, dict):
                    new_tokens = mapped_result.get("tokens", [])
                    new_raw_tokens = mapped_result.get("raw_tokens", [])

                    # Only apply if we actually found something, OR if there's no remote tokens.
                    # But the simplest is to only apply non-empty physical results to avoid flickering.
                    if new_tokens or new_raw_tokens:
                        from light_map.common_types import DetectionResult, ResultType

                        res = DetectionResult(
                            timestamp=time.perf_counter_ns(),
                            type=ResultType.ARUCO,
                            data={"tokens": new_tokens, "raw_tokens": new_raw_tokens},
                        )
                        self.state.apply(res)

                # NOTE: We DO NOT clear raw_aruco here anymore.
                # Calibration scenes (e.g. Extrinsics) rely on the raw corners
                # being available in the context. If we clear it, they get empty data.
                # Since WorldState.apply already implements a change-check,
                # we won't trigger redundant renders if the same results arrive.
                # raw_aruco will be cleared in WorldState.clear_dirty() after the render.

        # 4. Process Temporal Events
        self.events.check()

        # 5. Poll Hardware Input
        key = cv2.waitKey(1)
        self.input.update_keyboard(key)

        # 6. Get Semantic Actions
        actions = self.input.get_actions()

        # 6.5 Update State Mirror for Remote Driver
        if self.state_mirror is not None:
            self.state_mirror["world"] = self.state.to_dict()
            self.state_mirror["tokens"] = [t.to_dict() for t in self.state.tokens]

            # For menu, we need to extract current regions if available
            if self.state.menu_state:
                # We'll need a way to get bounds. For now, just title and depth.
                self.state_mirror["menu"] = {
                    "title": self.state.menu_state.current_menu_title,
                    "depth": 0,  # MenuState doesn't expose depth directly now
                    "items": [
                        item.title for item in self.state.menu_state.active_items
                    ],
                }
            else:
                self.state_mirror["menu"] = None

        # 7. Periodic Performance Reporting (when debug is active)
        if self.debug_mode:
            current_time = time.perf_counter()
            if current_time - self._last_report_time > 5.0:
                report = self.instrument.get_report()
                if report:
                    logging.debug(
                        f"Performance Report (P95 ms): { {k: v['p95_ms'] for k, v in report.items() if isinstance(v, dict) and 'p95_ms' in v} }"
                    )
                self._last_report_time = current_time

        return actions

    def _drain_queues(self):
        """Pulls all pending results from detector queues and applies them to WorldState."""
        # Check combined results queue
        while not self.manager.results_queue.empty():
            try:
                res = self.manager.results_queue.get_nowait()
                if isinstance(res, DetectionResult):
                    # Record hops from metadata
                    md = res.metadata
                    ts = res.timestamp
                    if "ts_shm_pushed" in md:
                        self.instrument.record_interval(
                            "capture_to_shm", md["ts_shm_pushed"] - ts
                        )
                    if "ts_shm_pulled" in md and "ts_shm_pushed" in md:
                        self.instrument.record_interval(
                            "shm_transit_to_worker",
                            md["ts_shm_pulled"] - md["ts_shm_pushed"],
                        )
                    if "ts_work_done" in md and "ts_shm_pulled" in md:
                        self.instrument.record_interval(
                            "worker_proc_time", md["ts_work_done"] - md["ts_shm_pulled"]
                        )
                    if "ts_queue_pushed" in md and "ts_work_done" in md:
                        self.instrument.record_interval(
                            "queue_wait_worker",
                            md["ts_queue_pushed"] - md["ts_work_done"],
                        )

                    if "ts_queue_pushed" in md:
                        self.instrument.record_interval(
                            "queue_transit_to_main",
                            time.perf_counter_ns() - md["ts_queue_pushed"],
                        )

                    self.state.apply(res)
                    self.instrument.record_detection(res.timestamp)
            except Exception:
                break

    def run(self, render_callback):
        """Starts the high-frequency polling loop."""
        self.is_running = True
        logging.info("Main loop started.")

        try:
            while self.is_running:
                start_time = time.perf_counter()

                # 1. Process State
                actions = self.tick()

                # 2. Trigger Render (Layered Renderer handles dirty states)
                ts_to_render = self.state.last_frame_timestamp
                with track_wait("render_time", self.instrument):
                    # We always call render_callback so InteractiveApp can check for dirty scenes
                    # or remote inputs even if no new camera frame arrived.
                    did_render = render_callback(self.state, actions)

                if did_render:
                    if ts_to_render > 0:
                        self.instrument.record_render(ts_to_render)
                    self.state.clear_raw_aruco()

                # 3. Handle Frame Rate
                elapsed = time.perf_counter() - start_time
                wait_time = max(0.001, self.frame_time - elapsed)
                time.sleep(wait_time)

        except KeyboardInterrupt:
            logging.info("Interrupted by user.")
        finally:
            logging.info("Main loop finished loop execution.")
            self.stop()

    def stop(self):
        self.is_running = False
        logging.info("Main loop stopping...")
        if self.producer:
            self.producer.close()
        self.manager.stop()
