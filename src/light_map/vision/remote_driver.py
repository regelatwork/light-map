from __future__ import annotations
import time
import logging
import uvicorn
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
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
        logging.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        # Iterate over a copy to allow safe removal during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


def create_app(results_queue: Queue, stop_event: Event, state_mirror: Dict[str, Any]):
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: Start the broadcast loop
        async def broadcast_loop():
            logging.info("Starting WebSocket state broadcast loop.")
            while not stop_event.is_set():
                if manager.active_connections:
                    state = {
                        "world": state_mirror.get("world", {}),
                        "tokens": state_mirror.get("tokens", []),
                        "menu": state_mirror.get("menu", {}),
                        "timestamp": time.monotonic(),
                    }
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
    port: int = 8000,
    host: str = "127.0.0.1",
):
    """Worker process entry point for the Remote Driver."""
    logging.info(f"Starting Remote Driver on {host}:{port}")
    app = create_app(results_queue, stop_event, state_mirror)

    config = uvicorn.Config(
        app, host=host, port=port, log_level="info", access_log=False
    )
    server = uvicorn.Server(config)

    # Run the server in the current process
    # We don't use server.run() because we might want to check stop_event
    # but uvicorn handles signals. For simplicity in a worker process:
    server.run()
