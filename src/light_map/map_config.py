import json
import os
import numpy as np
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional

STATE_FILE = "map_state.json"


@dataclass
class ViewportState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0


@dataclass
class MapEntry:
    scale_factor: float = 1.0
    viewport: ViewportState = field(default_factory=ViewportState)


@dataclass
class GlobalMapConfig:
    projector_ppi: float = 96.0
    last_used_map: Optional[str] = None


@dataclass
class MapConfigData:
    global_settings: GlobalMapConfig = field(default_factory=GlobalMapConfig)
    maps: Dict[str, MapEntry] = field(default_factory=dict)


class MapConfigManager:
    def __init__(self, filename: str = STATE_FILE):
        self.filename = filename
        self.data = self._load()

    def _load(self) -> MapConfigData:
        if not os.path.exists(self.filename):
            return MapConfigData()

        try:
            with open(self.filename, "r") as f:
                raw = json.load(f)

            # Deserialize
            global_data = raw.get("global", {})
            global_settings = GlobalMapConfig(
                projector_ppi=global_data.get("projector_ppi", 96.0),
                last_used_map=global_data.get("last_used_map"),
            )

            maps = {}
            for name, entry_data in raw.get("maps", {}).items():
                vp_data = entry_data.get("viewport", {})
                viewport = ViewportState(
                    x=vp_data.get("x", 0.0),
                    y=vp_data.get("y", 0.0),
                    zoom=vp_data.get("zoom", 1.0),
                    rotation=vp_data.get("rotation", 0.0),
                )
                maps[name] = MapEntry(
                    scale_factor=entry_data.get("scale_factor", 1.0), viewport=viewport
                )

            return MapConfigData(global_settings=global_settings, maps=maps)

        except Exception as e:
            print(f"Error loading map config: {e}")
            return MapConfigData()

    def save(self):
        try:
            # Serialize
            data_dict = {
                "global": asdict(self.data.global_settings),
                "maps": {k: asdict(v) for k, v in self.data.maps.items()},
            }

            def default(obj):
                if isinstance(obj, (np.integer, np.floating, np.bool_)):
                    return obj.item()
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                return str(obj)

            with open(self.filename, "w") as f:
                json.dump(data_dict, f, indent=2, default=default)
        except Exception as e:
            print(f"Error saving map config: {e}")

    def get_ppi(self) -> float:
        return self.data.global_settings.projector_ppi

    def set_ppi(self, ppi: float):
        self.data.global_settings.projector_ppi = ppi
        self.save()

    def get_map_viewport(self, map_name: str) -> ViewportState:
        if map_name in self.data.maps:
            return self.data.maps[map_name].viewport
        return ViewportState()

    def save_map_viewport(
        self, map_name: str, x: float, y: float, zoom: float, rotation: float
    ):
        if map_name not in self.data.maps:
            self.data.maps[map_name] = MapEntry()

        vp = self.data.maps[map_name].viewport
        vp.x = x
        vp.y = y
        vp.zoom = zoom
        vp.rotation = rotation
        self.save()
