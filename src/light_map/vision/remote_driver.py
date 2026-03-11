from __future__ import annotations
import time
import logging
import uvicorn
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import threading
import cv2
from light_map.vision.frame_producer import FrameProducer
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from multiprocessing import Queue, Event

from light_map.common_types import DetectionResult, ResultType, Token, GestureType
from light_map.core.scene import HandInput


class RemoteHandInput(BaseModel):
    x: int
    y: int
    gesture: GestureType = GestureType.NONE


class RemoteWorldHandInput(BaseModel):
    world_x: float
    world_y: float
    gesture: GestureType = GestureType.NONE


class RemoteToken(BaseModel):
    id: int
    x: float
    y: float
    z: float = 0.0
    angle: float = 0.0


class ViewportConfig(BaseModel):
    zoom: Optional[float] = None
    pan_x: Optional[float] = None
    pan_y: Optional[float] = None
    rotation: Optional[float] = None


class GridConfig(BaseModel):
    offset_x: float
    offset_y: float


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(
            f"WebSocket client connected. Total: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(
                f"WebSocket client disconnected. Total: {len(self.active_connections)}"
            )

    async def broadcast(self, message: dict):
        # Iterate over a copy to allow safe removal during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


def create_app(
    results_queue: Queue,
    stop_event: Event,
    state_mirror: Dict[str, Any],
    shm_name: str = None,
    lock: Any = None,
    width: int = 1920,
    height: int = 1080,
    num_consumers: int = 2,
):
    manager = ConnectionManager()

    # Shared state for video feed
    video_state = {"latest_jpeg": b"", "new_frame_event": None, "loop": None}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        video_state["loop"] = asyncio.get_running_loop()
        video_state["new_frame_event"] = asyncio.Event()

        def frame_capture_loop():
            if not shm_name or not lock:
                logging.info("Video feed disabled (no SHM provided).")
                return

            try:
                producer = FrameProducer(
                    shm_name=shm_name,
                    width=width,
                    height=height,
                    num_consumers=num_consumers,
                )
                producer.lock = lock
                last_processed_ts = -1

                logging.info(f"Video stream capture loop started (SHM: {shm_name})")
                while not stop_event.is_set():
                    latest_ts = producer.get_latest_timestamp()
                    if latest_ts is None or latest_ts <= last_processed_ts:
                        time.sleep(0.01)
                        continue

                    try:
                        frame_view = producer.get_latest_frame()
                        if frame_view is None:
                            time.sleep(0.01)
                            continue

                        # Resize for web stream to reduce bandwidth
                        h, w = frame_view.shape[:2]
                        scale = min(1280 / w, 720 / h)
                        new_w, new_h = int(w * scale), int(h * scale)
                        frame_copy = cv2.resize(frame_view, (new_w, new_h))
                    finally:
                        producer.release()
                        frame_view = None

                    ret, jpeg = cv2.imencode(
                        ".jpg", frame_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                    )
                    if ret:
                        video_state["latest_jpeg"] = jpeg.tobytes()
                        # Safely notify async clients
                        if video_state["loop"] and not video_state["loop"].is_closed():
                            video_state["loop"].call_soon_threadsafe(
                                video_state["new_frame_event"].set
                            )

                    last_processed_ts = latest_ts
            except Exception as e:
                logging.error(f"Video capture loop error: {e}", exc_info=True)
            finally:
                if "producer" in locals():
                    producer.close()
                logging.info("Video stream capture loop stopped.")

        video_thread = threading.Thread(target=frame_capture_loop, daemon=True)
        video_thread.start()

        # Startup: Start the broadcast loop

        async def broadcast_loop():
            logging.info("Starting WebSocket state broadcast loop.")
            while not stop_event.is_set():
                if manager.active_connections:
                    world = state_mirror.get("world", {})
                    state = {
                        "world": world,
                        "tokens": state_mirror.get("tokens", []),
                        "menu": state_mirror.get("menu", {}),
                        "config": state_mirror.get("config", {}),
                        "timestamp": time.monotonic(),
                    }
                    # Hoist grid metadata to top level for frontend SystemState compatibility
                    for key in [
                        "grid_spacing_svg",
                        "grid_origin_svg_x",
                        "grid_origin_svg_y",
                    ]:
                        if key in world:
                            state[key] = world[key]

                    await manager.broadcast(state)
                await asyncio.sleep(0.033)  # ~30Hz
            logging.info("WebSocket state broadcast loop stopped.")

        broadcast_task = asyncio.create_task(broadcast_loop())
        yield
        # Shutdown: Stop the broadcast loop and wait for it to finish
        stop_event.set()
        try:
            await asyncio.wait_for(broadcast_task, timeout=1.0)
        except asyncio.TimeoutError:
            logging.warning("Broadcast task did not stop in time, cancelling.")
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="Light Map Remote Driver", lifespan=lifespan)

    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/video_feed")
    async def video_feed():
        async def frame_generator():
            while not stop_event.is_set():
                if not video_state["new_frame_event"]:
                    await asyncio.sleep(0.1)
                    continue

                await video_state["new_frame_event"].wait()
                video_state["new_frame_event"].clear()

                jpeg_bytes = video_state["latest_jpeg"]
                if jpeg_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                    )

        if not shm_name:
            return {"error": "Video feed not available"}

        return StreamingResponse(
            frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    @app.get("/health")
    def health():
        return {"status": "ok", "stop_event": stop_event.is_set()}

    @app.websocket("/ws/state")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                # Keep connection open, handle incoming heartbeat/messages
                await websocket.receive_text()
        except Exception:
            manager.disconnect(websocket)

    @app.post("/input/hands")
    def inject_hands(hands: List[RemoteHandInput]):
        """Injects virtual hand inputs into the results queue."""
        processed_hands = []
        for h in hands:
            processed_hands.append(
                HandInput(
                    gesture=h.gesture,
                    proj_pos=(h.x, h.y),
                    unit_direction=(0.0, 0.0),  # Default to no specific direction
                    raw_landmarks=None,  # Virtual hands don't have landmarks
                )
            )

        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.HANDS,
            data=processed_hands,
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_hands)}

    @app.post("/input/hands/world")
    def inject_hands_world(hands: List[RemoteWorldHandInput]):
        """Injects virtual hand inputs using world coordinates."""
        hands_data = [
            h.model_dump() if hasattr(h, "model_dump") else h.dict() for h in hands
        ]
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": "INJECT_HANDS_WORLD", "hands": hands_data},
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(hands)}

    @app.post("/input/tokens")
    def inject_tokens(tokens: List[RemoteToken]):
        """Injects virtual ArUco tokens into the results queue."""
        processed_tokens = []
        for t in tokens:
            processed_tokens.append(
                Token(id=t.id, world_x=t.x, world_y=t.y, world_z=t.z, confidence=1.0)
            )

        # Wrapped as ARUCO result type
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ARUCO,
            data={"tokens": processed_tokens, "raw_tokens": processed_tokens},
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_tokens)}

    @app.post("/input/action")
    def inject_action(action: str, payload: Optional[str] = None):
        """Injects a manual application action (like SYNC_VISION)."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": action, "payload": payload},
        )
        results_queue.put(res)
        return {"status": "injected", "action": action}

    @app.post("/map/zoom")
    def zoom_map(delta: float):
        """Injects a zoom action for the map system."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": "ZOOM", "delta": delta},
        )
        results_queue.put(res)
        return {"status": "injected", "delta": delta}

    @app.post("/config/viewport")
    def set_viewport(config: ViewportConfig):
        data = {"action": "SET_VIEWPORT"}
        if config.zoom is not None:
            data["zoom"] = config.zoom
        if config.pan_x is not None:
            data["pan_x"] = config.pan_x
        if config.pan_y is not None:
            data["pan_y"] = config.pan_y
        if config.rotation is not None:
            data["rotation"] = config.rotation

        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data=data,
        )
        results_queue.put(res)
        return {"status": "injected"}

    @app.post("/config/grid")
    def set_grid_config(config: GridConfig):
        """Update grid offset configuration."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "UPDATE_GRID",
                "offset_x": config.offset_x,
                "offset_y": config.offset_y,
            },
        )
        results_queue.put(res)
        return {"status": "injected"}

    @app.get("/config")
    def get_config():
        return state_mirror.get("config", {})

    @app.get("/state/menu")
    def get_menu_state():
        return state_mirror.get("menu", {})

    @app.get("/state/world")
    def get_world_state():
        return state_mirror.get("world", {})

    @app.get("/state/tokens")
    def get_tokens():
        return state_mirror.get("tokens", [])

    @app.get("/state/blockers")
    def get_blockers():
        return state_mirror.get("world", {}).get("blockers", [])

    @app.get("/state/dwell")
    def get_dwell():
        return state_mirror.get("world", {}).get("dwell_state", {})

    @app.get("/state/logs")
    def get_logs(lines: int = 100):
        try:
            from light_map.core.storage import StorageManager

            log_path = StorageManager().get_state_path("light_map.log")
            if not os.path.exists(log_path):
                return {"logs": []}
            with open(log_path, "r") as f:
                all_lines = f.readlines()
                return {"logs": [line.strip() for line in all_lines[-lines:]]}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/map/svg")
    def get_map_svg():
        current_map = state_mirror.get("config", {}).get("current_map_path")
        if current_map and os.path.exists(current_map):
            from fastapi.responses import FileResponse

            return FileResponse(current_map, media_type="image/svg+xml")
        return {"error": "No map loaded"}

    @app.get("/map/fow")
    def get_map_fow():
        current_map = state_mirror.get("config", {}).get("current_map_path")
        if current_map:
            from light_map.core.storage import StorageManager
            import hashlib

            stem = os.path.splitext(os.path.basename(current_map))[0]
            path_hash = hashlib.md5(current_map.encode()).hexdigest()[:8]
            fow_path = os.path.join(
                StorageManager().get_data_dir(), "fow", f"{stem}_{path_hash}", "fow.png"
            )
            if os.path.exists(fow_path):
                from fastapi.responses import FileResponse

                return FileResponse(
                    fow_path,
                    media_type="image/png",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                )
        return {"error": "No FOW available"}

    @app.get("/maps")
    def get_maps():
        """Returns a list of registered maps from the MapConfigManager."""
        maps_dict = state_mirror.get("maps", {})
        return [
            {"path": path, "name": info.get("name", os.path.basename(path))}
            for path in maps_dict.keys()
            for info in [maps_dict[path]]
        ]

    @app.post("/map/load")
    def load_map(path: str, load_session: bool = True):
        """Triggers a map load action in the main application."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "LOAD_MAP",
                "map_file": path,
                "load_session": load_session,
            },
        )
        results_queue.put(res)
        return {"status": "injected", "map": path}

    @app.get("/state/clock")
    def get_clock():
        return {"time_monotonic": time.monotonic()}

    # Mount static files for the frontend dashboard
    # MUST BE LAST to avoid overriding API routes
    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../frontend/dist")
    )
    if os.path.exists(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        logging.warning(
            f"Frontend dist directory not found at {frontend_dist}. Dashboard UI will not be available."
        )

    return app


def remote_driver_worker(
    results_queue: Queue,
    stop_event: Event,
    state_mirror: Dict[str, Any],
    shm_name: str = None,
    lock: Any = None,
    port: int = 8000,
    host: str = "127.0.0.1",
    width: int = 1920,
    height: int = 1080,
    num_consumers: int = 2,
):
    """Worker process entry point for the Remote Driver."""
    logging.info(f"Starting Remote Driver on {host}:{port}")
    app = create_app(
        results_queue,
        stop_event,
        state_mirror,
        shm_name,
        lock,
        width,
        height,
        num_consumers,
    )

    config = uvicorn.Config(
        app, host=host, port=port, log_level="info", access_log=False
    )
    server = uvicorn.Server(config)

    # Run the server in the current process
    # We don't use server.run() because we might want to check stop_event
    # but uvicorn handles signals. For simplicity in a worker process:
    server.run()
