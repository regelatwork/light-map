from __future__ import annotations
import time
import logging
import uvicorn
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Header, Response, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import threading
import cv2
import numpy as np
import fastapi.encoders
import fastapi.routing
from light_map.vision.frame_producer import FrameProducer
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from multiprocessing import Queue, Event

from light_map.common_types import DetectionResult, ResultType, Token, GestureType
from light_map.core.scene import HandInput


# --- Global monkeypatch for FastAPI to handle NumPy types ---
_original_jsonable_encoder = fastapi.encoders.jsonable_encoder


def custom_jsonable_encoder(obj: Any, **kwargs: Any) -> Any:
    """Extension of jsonable_encoder that handles NumPy arrays and scalars."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return _original_jsonable_encoder(obj, **kwargs)


# Apply the monkeypatch to both the encoders module and the routing module's local reference
fastapi.encoders.jsonable_encoder = custom_jsonable_encoder
fastapi.routing.jsonable_encoder = custom_jsonable_encoder
# -----------------------------------------------------------


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


class TokenUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    type: Optional[str] = None
    profile: Optional[str] = None
    size: Optional[int] = None
    height_mm: Optional[float] = None
    is_map_override: Optional[bool] = None


class ProfileUpdate(BaseModel):
    name: str
    size: int
    height_mm: float


class ViewportConfig(BaseModel):
    zoom: Optional[float] = None
    pan_x: Optional[float] = None
    pan_y: Optional[float] = None
    rotation: Optional[float] = None


class GridConfig(BaseModel):
    offset_x: float
    offset_y: float
    spacing: Optional[float] = None


class SystemConfigUpdate(BaseModel):
    enable_hand_masking: Optional[bool] = None
    enable_aruco_masking: Optional[bool] = None
    parallax_factor: Optional[float] = None
    gm_position: Optional[str] = None


def numpy_to_python(obj: Any) -> Any:
    """Recursively convert NumPy types to native Python types for JSON serialization."""
    return fastapi.encoders.jsonable_encoder(obj)


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
    allowed_origins: Optional[List[str]] = None,
):
    manager = ConnectionManager()

    def get_formatted_state(mirror):
        """Fetch and format state from mirror for WebSocket broadcast."""
        try:
            fetched = {
                "world": mirror.get("world", {}),
                "tokens": mirror.get("tokens", []),
                "menu": mirror.get("menu", None),
                "config": mirror.get("config", {}),
                "maps": mirror.get("maps", {}),
            }
            world = fetched["world"]
            state = {
                "world": world,
                "tokens": fetched["tokens"],
                "menu": fetched["menu"],
                "config": fetched["config"],
                "maps": fetched["maps"],
                "timestamp": time.monotonic(),
            }
            # Hoist grid and version metadata to top level for frontend SystemState compatibility
            for key in [
                "grid_spacing_svg",
                "grid_origin_svg_x",
                "grid_origin_svg_y",
                "map_version",
                "menu_version",
                "tokens_version",
                "raw_aruco_version",
                "hands_version",
                "scene_version",
                "notifications_version",
                "viewport_version",
                "visibility_version",
                "fow_version",
            ]:
                if key in world:
                    state[key] = world[key]
            return numpy_to_python(state)
        except Exception as e:
            if not stop_event.is_set():
                logging.error(f"Error fetching state from mirror: {e}")
            return None

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
                last_processed_timestamp = -1

                logging.info(f"Video stream capture loop started (SHM: {shm_name})")
                while not stop_event.is_set():
                    latest_timestamp = producer.get_latest_timestamp()
                    if (
                        latest_timestamp is None
                        or latest_timestamp <= last_processed_timestamp
                    ):
                        time.sleep(0.01)
                        continue

                    try:
                        frame_view = producer.get_latest_frame()
                        if frame_view is None:
                            time.sleep(0.01)
                            continue

                        # Resize for web stream to reduce bandwidth
                        frame_height, frame_width = frame_view.shape[:2]
                        scale = min(1280 / frame_width, 720 / frame_height)
                        new_width, new_height = (
                            int(frame_width * scale),
                            int(frame_height * scale),
                        )
                        frame_copy = cv2.resize(frame_view, (new_width, new_height))
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

                    last_processed_timestamp = latest_timestamp
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
                    try:
                        state = await asyncio.to_thread(
                            get_formatted_state, state_mirror
                        )
                        if state:
                            await manager.broadcast(state)
                    except Exception as e:
                        if not stop_event.is_set():
                            logging.error(f"Broadcast loop error: {e}")
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

    # Default to common local origins if none specified
    if not allowed_origins:
        allowed_origins = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
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
        # Send initial state immediately to avoid waiting for the next broadcast loop
        try:
            initial_state = await asyncio.to_thread(get_formatted_state, state_mirror)
            if initial_state:
                await websocket.send_json(initial_state)
        except Exception as e:
            logging.error(f"Error sending initial state: {e}")

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
        for hand in hands:
            processed_hands.append(
                HandInput(
                    gesture=hand.gesture,
                    proj_pos=(hand.x, hand.y),
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
            hand.model_dump() if hasattr(hand, "model_dump") else hand.dict()
            for hand in hands
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
        for token in tokens:
            processed_tokens.append(
                Token(
                    id=token.id,
                    world_x=token.x,
                    world_y=token.y,
                    world_z=token.z,
                    confidence=1.0,
                )
            )

        # Wrapped as ARUCO result type
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ARUCO,
            data={"tokens": processed_tokens, "raw_tokens": processed_tokens},
        )
        res.metadata["source"] = "remote"
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_tokens)}

    @app.post("/input/aruco_corners")
    def inject_aruco_corners(corners: List[List[List[float]]], ids: List[int]):
        """Injects raw ArUco corners for testing mask rendering."""
        try:
            # Convert list of lists to list of numpy arrays for consistency
            marker_corners = [np.array(c, dtype=np.float32) for c in corners]
            res = DetectionResult(
                timestamp=time.perf_counter_ns(),
                type=ResultType.ARUCO,
                data={"corners": marker_corners, "ids": ids},
            )
            results_queue.put(res)
            return {"status": "injected", "count": len(ids)}
        except Exception as e:
            logging.error(f"Error in inject_aruco_corners: {e}", exc_info=True)
            raise e

    @app.put("/state/tokens/{token_id}")
    def update_token(token_id: int, update: TokenUpdate):
        """Updates the properties (name, color, type, profile, size, height_mm) of a specific token."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "UPDATE_TOKEN",
                "id": token_id,
                "name": update.name,
                "color": update.color,
                "type": update.type,
                "profile": update.profile,
                "size": update.size,
                "height_mm": update.height_mm,
                "is_map_override": update.is_map_override,
            },
        )
        results_queue.put(res)
        return {"status": "update_queued", "id": token_id}

    @app.delete("/state/tokens/{token_id}")
    def delete_token(token_id: int):
        """Removes a global definition for a specific token."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "DELETE_TOKEN",
                "id": token_id,
            },
        )
        results_queue.put(res)
        return {"status": "delete_queued", "id": token_id}

    @app.delete("/state/tokens/{token_id}/override")
    def delete_token_override(token_id: int):
        """Removes a map-specific override for a specific token."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "DELETE_TOKEN_OVERRIDE",
                "id": token_id,
            },
        )
        results_queue.put(res)
        return {"status": "delete_queued", "id": token_id}

    @app.put("/state/profiles")
    def update_profile(update: ProfileUpdate):
        """Updates or creates a token profile (shared template)."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "UPDATE_TOKEN_PROFILE",
                "name": update.name,
                "size": update.size,
                "height_mm": update.height_mm,
            },
        )
        results_queue.put(res)
        return {"status": "update_queued", "name": update.name}

    @app.delete("/state/profiles/{name}")
    def delete_profile(name: str):
        """Removes a token profile."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={
                "action": "DELETE_TOKEN_PROFILE",
                "name": name,
            },
        )
        results_queue.put(res)
        return {"status": "delete_queued", "name": name}

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
                "spacing": config.spacing,
            },
        )
        results_queue.put(res)
        return {"status": "injected"}

    @app.post("/config/system")
    def update_system_config(config: SystemConfigUpdate):
        """Update global system settings."""
        data = {"action": "UPDATE_SYSTEM_CONFIG"}
        if config.enable_hand_masking is not None:
            data["enable_hand_masking"] = config.enable_hand_masking
        if config.enable_aruco_masking is not None:
            data["enable_aruco_masking"] = config.enable_aruco_masking
        if config.parallax_factor is not None:
            data["parallax_factor"] = config.parallax_factor
        if config.gm_position is not None:
            data["gm_position"] = config.gm_position

        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data=data,
        )
        results_queue.put(res)
        return {"status": "injected"}

    @app.post("/menu/interact")
    def interact_menu(index: int = Query(...)):
        """Trigger a menu item by index."""
        logging.debug(f"RemoteDriver: Received /menu/interact?index={index}")
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": "MENU_INTERACT", "index": index},
        )
        results_queue.put(res)
        return {"status": "injected", "index": index}

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
    def get_map_svg(if_none_match: str = Header(None)):
        current_map = state_mirror.get("config", {}).get("current_map_path")
        if current_map and os.path.exists(current_map):
            from fastapi.responses import FileResponse

            stat = os.stat(current_map)
            etag = f'"{int(stat.st_mtime)}-{stat.st_size}"'
            if if_none_match == etag:
                return Response(status_code=304)

            return FileResponse(
                current_map,
                media_type="image/svg+xml",
                headers={"ETag": etag, "Cache-Control": "no-cache"},
            )
        return {"error": "No map loaded"}

    @app.get("/map/fow")
    def get_map_fow(if_none_match: str = Header(None)):
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

                stat = os.stat(fow_path)
                etag = f'"{int(stat.st_mtime)}-{stat.st_size}"'
                if if_none_match == etag:
                    return Response(status_code=304)

                return FileResponse(
                    fow_path,
                    media_type="image/png",
                    headers={"ETag": etag, "Cache-Control": "no-cache"},
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
    allowed_origins: Optional[List[str]] = None,
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
        allowed_origins=allowed_origins,
    )

    config = uvicorn.Config(
        app, host=host, port=port, log_level="info", access_log=False
    )
    server = uvicorn.Server(config)

    # Run the server in the current process
    # We don't use server.run() because we might want to check stop_event
    # but uvicorn handles signals. For simplicity in a worker process:
    server.run()
