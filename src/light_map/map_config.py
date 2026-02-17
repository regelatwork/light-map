import json
import os
import glob
import datetime
import numpy as np
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, List
from light_map.common_types import ViewportState, TokenDetectionAlgorithm
from light_map.session_manager import SessionManager

STATE_FILE = "map_state.json"


@dataclass
class MapEntry:
    scale_factor: float = 1.0
    viewport: ViewportState = field(default_factory=ViewportState)
    # Grid Scaling Fields
    grid_spacing_svg: float = 0.0  # Default to 0.0 (Unknown)
    grid_origin_svg_x: float = 0.0
    grid_origin_svg_y: float = 0.0
    physical_unit_inches: float = 1.0  # e.g. 1.0 for 1 inch
    scale_factor_1to1: float = 1.0  # Calculated zoom level for 1:1 scale
    last_seen: str = ""  # ISO 8601 timestamp


@dataclass
class GlobalMapConfig:
    projector_ppi: float = 96.0
    flash_intensity: int = 255
    last_used_map: Optional[str] = None
    detection_algorithm: TokenDetectionAlgorithm = TokenDetectionAlgorithm.FLASH


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
                flash_intensity=global_data.get("flash_intensity", 255),
                last_used_map=global_data.get("last_used_map"),
                detection_algorithm=TokenDetectionAlgorithm(
                    global_data.get("detection_algorithm", "FLASH")
                ),
            )

            maps = {}
            raw_maps = raw.get("maps", {})
            for name, entry_data in raw_maps.items():
                vp_data = entry_data.get("viewport", {})
                viewport = ViewportState(
                    x=vp_data.get("x", 0.0),
                    y=vp_data.get("y", 0.0),
                    zoom=vp_data.get("zoom", 1.0),
                    rotation=vp_data.get("rotation", 0.0),
                )
                maps[name] = MapEntry(
                    scale_factor=entry_data.get("scale_factor", 1.0),
                    viewport=viewport,
                    grid_spacing_svg=entry_data.get("grid_spacing_svg", 0.0),
                    grid_origin_svg_x=entry_data.get("grid_origin_svg_x", 0.0),
                    grid_origin_svg_y=entry_data.get("grid_origin_svg_y", 0.0),
                    physical_unit_inches=entry_data.get("physical_unit_inches", 1.0),
                    scale_factor_1to1=entry_data.get("scale_factor_1to1", 1.0),
                    last_seen=entry_data.get("last_seen", ""),
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

    def get_flash_intensity(self) -> int:
        return self.data.global_settings.flash_intensity

    def set_flash_intensity(self, intensity: int):
        self.data.global_settings.flash_intensity = max(0, min(255, intensity))
        self.save()

    def get_detection_algorithm(self) -> TokenDetectionAlgorithm:
        return self.data.global_settings.detection_algorithm

    def set_detection_algorithm(self, algorithm: TokenDetectionAlgorithm):
        self.data.global_settings.detection_algorithm = algorithm
        self.save()

    def get_map_viewport(self, map_name: str) -> ViewportState:
        map_name = os.path.abspath(map_name)
        if map_name in self.data.maps:
            return self.data.maps[map_name].viewport
        return ViewportState()

    def save_map_viewport(
        self, map_name: str, x: float, y: float, zoom: float, rotation: float
    ):
        map_name = os.path.abspath(map_name)
        if map_name not in self.data.maps:
            self.data.maps[map_name] = MapEntry()

        vp = self.data.maps[map_name].viewport
        vp.x = x
        vp.y = y
        vp.zoom = zoom
        vp.rotation = rotation
        self.save()

    def save_map_grid_config(
        self,
        map_name: str,
        grid_spacing_svg: float,
        grid_origin_svg_x: float,
        grid_origin_svg_y: float,
        physical_unit_inches: float,
        scale_factor_1to1: float,
    ):
        map_name = os.path.abspath(map_name)
        if map_name not in self.data.maps:
            self.data.maps[map_name] = MapEntry()

        entry = self.data.maps[map_name]
        entry.grid_spacing_svg = grid_spacing_svg
        entry.grid_origin_svg_x = grid_origin_svg_x
        entry.grid_origin_svg_y = grid_origin_svg_y
        entry.physical_unit_inches = physical_unit_inches
        entry.scale_factor_1to1 = scale_factor_1to1
        self.save()

    def scan_for_maps(self, patterns: List[str]) -> List[str]:
        """
        Expands globs in patterns, checks for existence,
        adds new maps to config, and removes missing maps.
        Returns the updated list of known map filenames.
        """
        found_maps = set()

        # 1. Expand Globs
        for pattern in patterns:
            # Handle user expansion like ~
            expanded_pattern = os.path.expanduser(pattern)
            matched_files = glob.glob(expanded_pattern, recursive=True)

            for fpath in matched_files:
                abs_path = os.path.abspath(fpath)
                if os.path.isfile(abs_path):
                    # Simple extension check (can be expanded)
                    ext = os.path.splitext(abs_path)[1].lower()
                    if ext in [".svg", ".png", ".jpg", ".jpeg"]:
                        found_maps.add(abs_path)

        # 2. Update Config
        current_time = datetime.datetime.now().isoformat()

        # Add new maps or update timestamp
        for map_path in found_maps:
            if map_path not in self.data.maps:
                self.data.maps[map_path] = MapEntry(last_seen=current_time)
            else:
                self.data.maps[map_path].last_seen = current_time

        # 3. Prune Missing Maps
        # We only prune if we actually scanned something.
        # But wait, 'patterns' might be empty if we just want to re-verify existing?
        # If patterns is empty, we should probably check existence of all known maps.

        # Strategy: Always check existence of ALL known maps, regardless of scan patterns.
        # The 'patterns' are for ADDING. Pruning is for CLEANUP.

        to_remove = []
        for map_path in self.data.maps.keys():
            if not os.path.exists(map_path):
                to_remove.append(map_path)

        for map_path in to_remove:
            del self.data.maps[map_path]
            print(f"Pruned missing map: {map_path}")

        self.save()

        return list(self.data.maps.keys())

    def forget_map(self, filename: str):
        """Removes map from config."""
        filename = os.path.abspath(filename)
        if filename in self.data.maps:
            del self.data.maps[filename]
            self.save()

    def get_map_status(self, filename: str) -> Dict[str, bool]:
        """
        Returns {'calibrated': bool, 'has_session': bool}
        """
        filename = os.path.abspath(filename)
        entry = self.data.maps.get(filename)
        if not entry:
            return {"calibrated": False, "has_session": False}

        calibrated = entry.grid_spacing_svg > 0
        has_session = SessionManager.has_session(filename)

        return {"calibrated": calibrated, "has_session": has_session}
