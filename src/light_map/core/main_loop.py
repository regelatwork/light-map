import cv2
import time
import logging
from typing import Optional, List, Callable, Dict, Any
from light_map.state.world_state import WorldState
from light_map.state.temporal_event_manager import TemporalEventManager
from light_map.vision.infrastructure.process_manager import VisionProcessManager
from light_map.vision.infrastructure.frame_producer import FrameProducer
from light_map.input.input_manager import InputManager
from light_map.core.common_types import DetectionResult, ResultType, Action, Token
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
        events: Optional[TemporalEventManager] = None,
        time_provider=time.monotonic,
    ):
        self.state = world_state
        self.manager = process_manager
        self.input = input_manager
        self.producer = frame_producer
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self.aruco_mapper = aruco_mapper
        self.state_mirror = state_mirror
        self.time_provider = time_provider

        self.is_running = False
        self.instrument = LatencyInstrument()
        self.events = events or TemporalEventManager(time_provider=time_provider)
        self.debug_mode = False
        self._last_report_time = 0.0
        self._last_raw_aruco_ts = -1

    def tick(self) -> List[Action]:
        """Performs one iteration of the main loop."""
        current_mono = self.time_provider()

        # 1. Update Background from SHM
        producer = self.producer
        if producer:
            # Check for new frame
            ts = producer.get_latest_timestamp()
            if ts is not None and ts > self.state.last_frame_timestamp:
                self.instrument.record_capture(ts)

                with track_wait("shm_wait_main", self.instrument):
                    shm_view = producer.get_latest_frame()

                if shm_view is not None:
                    ts_shm_pushed = producer.get_shm_pushed_timestamp()
                    if ts_shm_pushed:
                        self.instrument.record_interval(
                            "capture_to_shm", ts_shm_pushed - ts
                        )
                        self.instrument.record_interval(
                            "shm_transit_to_main",
                            time.perf_counter_ns() - ts_shm_pushed,
                        )

                    self.state.update_from_frame(shm_view, ts)
                    producer.release()

        # 2. Drain Vision Results from Queues
        with track_wait("queue_wait_main", self.instrument):
            self._drain_queues(current_mono)

        # 3. Map Raw ArUco if available AND changed
        if self.state.raw_aruco_version != self._last_raw_aruco_ts:
            if self.aruco_mapper:
                mapped_result = self.aruco_mapper(self.state.raw_aruco)
                if isinstance(mapped_result, dict):
                    new_tokens = mapped_result.get("tokens", [])
                    new_raw_tokens = mapped_result.get("raw_tokens", [])

                    # Apply physical results to world state.
                    # We always apply even if empty to ensure tokens are cleared when removed.
                    res = DetectionResult(
                        timestamp=time.perf_counter_ns(),
                        type=ResultType.ARUCO,
                        data={"tokens": new_tokens, "raw_tokens": new_raw_tokens},
                    )
                    res.metadata["source"] = "physical"
                    self.state.apply(res, current_time=current_mono)

                # Track that we've processed this raw ArUco state
                self._last_raw_aruco_ts = self.state.raw_aruco_version

        # 4. Process Temporal Events
        event_actions = self.events.check()

        # 5. Poll Hardware Input
        key = cv2.waitKey(1)
        self.input.update_keyboard(key)

        # 6. Get Semantic Actions
        actions = self.input.get_actions()

        # Merge in actions produced by temporal events
        for res in event_actions:
            if isinstance(res, list):
                # Handle batch return if any callback returns multiple actions
                for r in res:
                    if r:
                        actions.append(r)
            elif res:
                # Add any truthy result (Action enum, string, etc.)
                actions.append(res)

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

    def _drain_queues(self, current_time: float) -> set[ResultType]:
        """Pulls all pending results from detector queues and applies them to WorldState."""
        seen_types = set()
        # Check combined results queue
        while not self.manager.results_queue.empty():
            try:
                res = self.manager.results_queue.get_nowait()
                if isinstance(res, DetectionResult):
                    seen_types.add(res.type)
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

                    self.state.apply(res, current_time=current_time)
                    self.instrument.record_detection(res.timestamp)
            except Exception:
                break
        return seen_types

    def run(self, render_callback):
        """Starts the high-frequency polling loop."""
        self.is_running = True
        logging.info("Main loop started.")

        try:
            while self.is_running:
                start_time = time.perf_counter()

                # 1. Process State
                actions = self.tick()

                # 2. Trigger Render (Layered Renderer handles version tracking)
                ts_to_render = self.state.last_frame_timestamp
                with track_wait("render_time", self.instrument):
                    # We always call render_callback so InteractiveApp can check for scene changes
                    # or remote inputs even if no new camera frame arrived.
                    did_render = render_callback(self.state, actions)

                if did_render:
                    if ts_to_render > 0:
                        self.instrument.record_render(ts_to_render)

                # 3. Handle Frame Rate
                elapsed = time.perf_counter() - start_time
                wait_time = max(0.001, self.frame_time - elapsed)
                time.sleep(wait_time)

        except KeyboardInterrupt:
            logging.info("Interrupted by user.")
        except Exception as e:
            logging.error("Main loop: Unexpected crash: %s", e, exc_info=True)
        finally:
            logging.info("Main loop finished loop execution.")
            self.stop()

    def stop(self):
        self.is_running = False
        logging.info("Main loop stopping...")
        if self.producer:
            self.producer.close()
            self.producer = None
        self.manager.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
