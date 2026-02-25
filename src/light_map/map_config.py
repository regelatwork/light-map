import os
import glob
import datetime
import logging
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, List, Any
from light_map.common_types import (
    ViewportState,
    TokenDetectionAlgorithm,
    GmPosition,
    NamingStyle,
)
from light_map.session_manager import SessionManager
from light_map.core.storage import StorageManager
from light_map.core.config_store import ConfigStore
from light_map.token_naming import generate_token_name

_DEFAULT_STORAGE = StorageManager()
STATE_FILE = _DEFAULT_STORAGE.get_config_path("map_state.json")


@dataclass
class SizeProfile:
    size: int = 1
    height_mm: float = 10.0


@dataclass
class ArucoDefinition:
    name: str
    type: str = "NPC"
    profile: Optional[str] = None
    size: Optional[int] = None
    height_mm: Optional[float] = None


@dataclass
class ResolvedToken:
    name: str
    type: str
    size: int
    height_mm: float
    is_known: bool = True


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
    aruco_overrides: Dict[int, ArucoDefinition] = field(default_factory=dict)


@dataclass
class GlobalMapConfig:
    projector_ppi: float = 96.0
    flash_intensity: int = 255
    last_used_map: Optional[str] = None
    detection_algorithm: TokenDetectionAlgorithm = TokenDetectionAlgorithm.FLASH
    token_profiles: Dict[str, SizeProfile] = field(
        default_factory=lambda: {
            "small": SizeProfile(1, 15.0),
            "medium": SizeProfile(1, 25.0),
            "large": SizeProfile(2, 40.0),
            "huge": SizeProfile(3, 60.0),
        }
    )
    aruco_defaults: Dict[int, ArucoDefinition] = field(default_factory=dict)
    # Masking Settings
    enable_hand_masking: bool = False
    hand_mask_padding: int = 30
    hand_mask_blur: int = 15
    gm_position: GmPosition = GmPosition.NONE
    naming_style: NamingStyle = NamingStyle.SCI_FI


@dataclass
class MapConfigData:
    global_settings: GlobalMapConfig = field(default_factory=GlobalMapConfig)
    maps: Dict[str, MapEntry] = field(default_factory=dict)


class MapConfigManager:
    def __init__(self, filename: Optional[str] = None, storage: Optional[Any] = None):
        self.storage = storage or _DEFAULT_STORAGE
        if filename:
            self.filename = filename
            if not storage:
                # If only filename is provided, assume tokens.json should be in the same dir
                self.tokens_filename = os.path.join(
                    os.path.dirname(filename), "tokens.json"
                )
            else:
                self.tokens_filename = self.storage.get_config_path("tokens.json")
        else:
            self.filename = self.storage.get_config_path("map_state.json")
            self.tokens_filename = self.storage.get_config_path("tokens.json")

        self.store = ConfigStore(self.filename)
        self.tokens_store = ConfigStore(self.tokens_filename)
        self.data = self._load()

    def _load(self) -> MapConfigData:
        try:
            raw = self.store.load(dict)
            tokens_raw = self.tokens_store.load(dict)

            if not raw and not tokens_raw:
                return MapConfigData()

            # Deserialize Global Settings
            global_data = raw.get("global", {})

            # Load Token Profiles
            raw_profiles = tokens_raw.get("token_profiles", {})
            token_profiles = {
                k: SizeProfile(v.get("size", 1), v.get("height_mm", 10.0))
                for k, v in raw_profiles.items()
            }
            if not token_profiles:  # If empty or missing, use defaults
                token_profiles = {
                    "small": SizeProfile(1, 15.0),
                    "medium": SizeProfile(1, 25.0),
                    "large": SizeProfile(2, 40.0),
                    "huge": SizeProfile(3, 60.0),
                }

            # Load ArUco Defaults
            raw_aruco = tokens_raw.get("aruco_defaults", {})
            aruco_defaults = {}
            for k, v in raw_aruco.items():
                try:
                    key = int(k)
                    aruco_defaults[key] = ArucoDefinition(
                        name=v.get("name", "Unknown"),
                        type=v.get("type", "NPC"),
                        profile=v.get("profile"),
                        size=v.get("size"),
                        height_mm=v.get("height_mm"),
                    )
                except ValueError:
                    pass

            global_settings = GlobalMapConfig(
                projector_ppi=global_data.get("projector_ppi", 96.0),
                flash_intensity=global_data.get("flash_intensity", 255),
                last_used_map=global_data.get("last_used_map"),
                detection_algorithm=TokenDetectionAlgorithm(
                    global_data.get("detection_algorithm", "FLASH")
                ),
                token_profiles=token_profiles,
                aruco_defaults=aruco_defaults,
                enable_hand_masking=global_data.get("enable_hand_masking", False),
                hand_mask_padding=global_data.get("hand_mask_padding", 30),
                hand_mask_blur=global_data.get("hand_mask_blur", 15),
                gm_position=GmPosition(global_data.get("gm_position", "None")),
                naming_style=NamingStyle(
                    global_data.get("naming_style", NamingStyle.SCI_FI)
                ),
            )

            # Deserialize Maps
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

                # Load Map Overrides
                raw_overrides = entry_data.get("aruco_overrides", {})
                aruco_overrides = {}
                for k, v in raw_overrides.items():
                    try:
                        key = int(k)
                        aruco_overrides[key] = ArucoDefinition(
                            name=v.get("name", "Unknown"),
                            type=v.get("type", "NPC"),
                            profile=v.get("profile"),
                            size=v.get("size"),
                            height_mm=v.get("height_mm"),
                        )
                    except ValueError:
                        pass

                maps[name] = MapEntry(
                    scale_factor=entry_data.get("scale_factor", 1.0),
                    viewport=viewport,
                    grid_spacing_svg=entry_data.get("grid_spacing_svg", 0.0),
                    grid_origin_svg_x=entry_data.get("grid_origin_svg_x", 0.0),
                    grid_origin_svg_y=entry_data.get("grid_origin_svg_y", 0.0),
                    physical_unit_inches=entry_data.get("physical_unit_inches", 1.0),
                    scale_factor_1to1=entry_data.get("scale_factor_1to1", 1.0),
                    last_seen=entry_data.get("last_seen", ""),
                    aruco_overrides=aruco_overrides,
                )

            return MapConfigData(global_settings=global_settings, maps=maps)

        except Exception as e:
            logging.error("Error loading map config: %s", e)
            return MapConfigData()

    def save(self):
        try:
            # Serialize Map State (excluding tokens)
            global_dict = asdict(self.data.global_settings)
            if "token_profiles" in global_dict:
                del global_dict["token_profiles"]
            if "aruco_defaults" in global_dict:
                del global_dict["aruco_defaults"]

            data_dict = {
                "global": global_dict,
                "maps": {k: asdict(v) for k, v in self.data.maps.items()},
            }
            self.store.save(data_dict)

            # Serialize Tokens
            tokens_dict = {
                "token_profiles": {
                    k: asdict(v)
                    for k, v in self.data.global_settings.token_profiles.items()
                },
                "aruco_defaults": {
                    str(k): asdict(v)
                    for k, v in self.data.global_settings.aruco_defaults.items()
                },
            }
            self.tokens_store.save(tokens_dict)
        except Exception as e:
            logging.error("Error saving map config: %s", e)

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

    def get_naming_style(self) -> NamingStyle:
        return self.data.global_settings.naming_style

    def set_naming_style(self, style: NamingStyle):
        self.data.global_settings.naming_style = style
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

        # 1. Expand Globs and handle comma-separated strings
        expanded_patterns = []
        for p in patterns:
            if "," in p:
                expanded_patterns.extend([part.strip() for part in p.split(",")])
            else:
                expanded_patterns.append(p)

        for pattern in expanded_patterns:
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
        to_remove = []
        for map_path in self.data.maps.keys():
            if not os.path.exists(map_path):
                to_remove.append(map_path)

        for map_path in to_remove:
            del self.data.maps[map_path]
            logging.info("Pruned missing map: %s", map_path)

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
        session_dir = None
        if self.storage:
            session_dir = os.path.join(self.storage.get_data_dir(), "sessions")
        has_session = SessionManager.has_session(filename, session_dir=session_dir)

        return {"calibrated": calibrated, "has_session": has_session}

    # --- New ArUco / Profile Methods ---

    def get_aruco_configs(self, map_name: Optional[str] = None) -> Dict[int, Dict]:
        """
        Returns a dictionary of all known ArUco IDs and their resolved properties
        for the current map (if provided) and global defaults.
        """
        # 1. Get all unique IDs from global and map-specific overrides
        all_ids = set(self.data.global_settings.aruco_defaults.keys())
        if map_name:
            map_name = os.path.abspath(map_name)
            if map_name in self.data.maps:
                all_ids.update(self.data.maps[map_name].aruco_overrides.keys())

        # 2. Resolve each ID
        configs = {}
        for aid in all_ids:
            resolved = self.resolve_token_profile(aid, map_name)
            configs[aid] = asdict(resolved)

        return configs

    def resolve_token_profile(
        self, aruco_id: int, map_name: Optional[str] = None
    ) -> ResolvedToken:
        """
        Resolves the full token profile for a given ArUco ID, considering:
        1. Map-specific overrides (if map_name provided)
        2. Global defaults
        3. Fallback to generic defaults
        """
        definition: Optional[ArucoDefinition] = None

        # 1. Check Map Override
        if map_name:
            map_name = os.path.abspath(map_name)
            if map_name in self.data.maps:
                definition = self.data.maps[map_name].aruco_overrides.get(aruco_id)

        # 2. Check Global Default
        if not definition:
            definition = self.data.global_settings.aruco_defaults.get(aruco_id)

        # 3. Fallback Generic if still not found
        if not definition:
            name = generate_token_name(
                aruco_id,
                map_name=map_name or "",
                style=self.data.global_settings.naming_style,
            )
            return ResolvedToken(
                name=name,
                type="NPC",
                size=1,
                height_mm=10.0,
                is_known=False,
            )

        # 4. Resolve dimensions
        # Start with defaults
        size = 1
        height_mm = 10.0

        # If profile is specified, apply it first
        if definition.profile:
            profile_def = self.data.global_settings.token_profiles.get(
                definition.profile
            )
            if profile_def:
                size = profile_def.size
                height_mm = profile_def.height_mm

        # Specific overrides take precedence
        if definition.size is not None:
            size = definition.size

        if definition.height_mm is not None:
            height_mm = definition.height_mm

        return ResolvedToken(
            name=definition.name, type=definition.type, size=size, height_mm=height_mm
        )

    def set_global_aruco_definition(
        self,
        aruco_id: int,
        name: str,
        type: str = "NPC",
        profile: Optional[str] = None,
        size: Optional[int] = None,
        height_mm: Optional[float] = None,
    ):
        """Helper to set a global definition."""
        self.data.global_settings.aruco_defaults[aruco_id] = ArucoDefinition(
            name=name, type=type, profile=profile, size=size, height_mm=height_mm
        )
        self.save()

    def set_map_aruco_override(
        self,
        map_name: str,
        aruco_id: int,
        name: str,
        type: str = "NPC",
        profile: Optional[str] = None,
        size: Optional[int] = None,
        height_mm: Optional[float] = None,
    ):
        """Helper to set a map override."""
        map_name = os.path.abspath(map_name)
        if map_name not in self.data.maps:
            self.data.maps[map_name] = MapEntry()

        self.data.maps[map_name].aruco_overrides[aruco_id] = ArucoDefinition(
            name=name, type=type, profile=profile, size=size, height_mm=height_mm
        )
        self.save()
