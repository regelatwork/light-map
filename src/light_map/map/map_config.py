import os
import glob
import datetime
import time
import logging
import hashlib
import json
import cv2
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, List, Any
from light_map.core.common_types import (
    ViewportState,
    TokenDetectionAlgorithm,
    GmPosition,
    NamingStyle,
    GridType,
)
from light_map.core.constants import (
    DEFAULT_TOKEN_HEIGHT_MM,
    DEFAULT_ARUCO_MASK_PADDING,
    DEFAULT_ARUCO_MASK_INTENSITY,
    DEFAULT_ARUCO_MASK_PERSISTENCE_S,
    DEFAULT_POINTER_OFFSET_MM,
)
from light_map.map.session_manager import SessionManager
from light_map.core.storage import StorageManager
from light_map.core.config_store import ConfigStore
from light_map.core.token_naming import generate_token_name

from light_map.core.config_schema import (
    GlobalConfigSchema,
    TokenConfigSchema,
    MapEntrySchema,
)
from light_map.core.config_utils import sync_pydantic_to_dataclass

# Add TYPE_CHECKING to avoid circular import with FogOfWarManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from light_map.map.fow_manager import FogOfWarManager

_DEFAULT_STORAGE = StorageManager()
STATE_FILE = _DEFAULT_STORAGE.get_config_path("map_state.json")


@dataclass
class SizeProfile:
    size: int = 1
    height_mm: float = DEFAULT_TOKEN_HEIGHT_MM


@dataclass
class ArucoDefinition:
    name: str
    type: str = "NPC"
    profile: Optional[str] = None
    size: Optional[int] = None
    height_mm: Optional[float] = None
    color: Optional[str] = None


@dataclass
class ResolvedToken:
    name: str
    type: str
    size: int
    height_mm: float
    is_known: bool = True
    color: Optional[str] = None


@dataclass
class MapEntry:
    scale_factor: float = 1.0
    viewport: ViewportState = field(default_factory=ViewportState)
    # Grid Scaling Fields
    grid_spacing_svg: float = 0.0  # Default to 0.0 (Unknown)
    grid_origin_svg_x: float = 0.0
    grid_origin_svg_y: float = 0.0
    grid_type: GridType = GridType.SQUARE
    physical_unit_inches: float = 1.0  # e.g. 1.0 for 1 inch
    scale_factor_1to1: float = 1.0  # Calculated zoom level for 1:1 scale
    last_seen: str = ""  # ISO 8601 timestamp
    aruco_overrides: Dict[int, ArucoDefinition] = field(default_factory=dict)
    fow_disabled: bool = False


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
            "huge": SizeProfile(3, DEFAULT_TOKEN_HEIGHT_MM),
        }
    )
    aruco_defaults: Dict[int, ArucoDefinition] = field(default_factory=dict)
    # Masking Settings
    enable_hand_masking: bool = False
    hand_mask_padding: int = 30
    enable_aruco_masking: bool = True
    aruco_mask_padding: int = DEFAULT_ARUCO_MASK_PADDING
    aruco_mask_intensity: int = DEFAULT_ARUCO_MASK_INTENSITY
    aruco_mask_persistence_s: float = DEFAULT_ARUCO_MASK_PERSISTENCE_S
    calibration_box_height_mm: float = 78.0
    calibration_box_width_mm: float = 188.0
    calibration_box_length_mm: float = 295.0
    use_projector_3d_model: bool = True
    projector_pos_x_override: Optional[float] = None
    projector_pos_y_override: Optional[float] = None
    projector_pos_z_override: Optional[float] = None
    gm_position: GmPosition = GmPosition.NONE
    naming_style: NamingStyle = NamingStyle.SCI_FI
    pointer_offset_mm: float = DEFAULT_POINTER_OFFSET_MM
    inspection_linger_duration: float = 10.0
    door_thickness_multiplier: float = 3.0


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
        self._last_issued_version = 0
        self._version = self._get_next_version()
        self.data = self._load()

    @property
    def version(self) -> int:
        return self._version

    @version.setter
    def version(self, value: int):
        self._version = value

    def update_global_settings(self, payload: Dict[str, Any]) -> None:
        """
        Validates the payload against GlobalConfigSchema and updates both
        the in-memory data and the on-disk storage.
        """
        # 1. Validate (handles typecasting and range checks)
        # Using partial update: we only validate what's in the payload
        validated = GlobalConfigSchema(**payload)

        # 2. Sync to internal dataclass
        sync_pydantic_to_dataclass(validated, self.data.global_settings)

        # 3. Persist to disk
        self.save()
        self.version = self._get_next_version()

    def _get_next_version(self) -> int:
        """Returns a strictly monotonic version number based on time.monotonic_ns()."""
        new_v = time.monotonic_ns()
        if new_v <= self._last_issued_version:
            new_v = self._last_issued_version + 1
        self._last_issued_version = new_v
        return new_v

    def _load(self) -> MapConfigData:
        try:
            raw = self.store.load(dict)
            tokens_raw = self.tokens_store.load(dict)

            # Fallback: if tokens_raw is empty, try looking in the project root
            if not tokens_raw or not tokens_raw.get("token_profiles"):
                root_tokens_path = os.path.join(os.getcwd(), "tokens.json")
                if (
                    os.path.exists(root_tokens_path)
                    and root_tokens_path != self.tokens_filename
                ):
                    logging.info(
                        f"MapConfig: Primary tokens.json empty, trying root fallback: {root_tokens_path}"
                    )
                    try:
                        with open(root_tokens_path, "r") as f:
                            root_tokens = json.load(f)
                            if root_tokens and root_tokens.get("token_profiles"):
                                tokens_raw = root_tokens
                                logging.info(
                                    "MapConfig: Successfully loaded tokens from root fallback."
                                )
                    except Exception as e:
                        logging.warning(
                            f"MapConfig: Failed to load root tokens fallback: {e}"
                        )

            if not raw and not tokens_raw:
                return MapConfigData()

            # 1. Global Settings
            global_raw = raw.get("global", {})
            try:
                # We use GlobalConfigSchema to handle defaults and validation
                validated_global = GlobalConfigSchema(**global_raw)
                global_settings = GlobalMapConfig()
                sync_pydantic_to_dataclass(validated_global, global_settings)
            except Exception as e:
                logging.warning(
                    f"MapConfig: Failed to validate global settings: {e}. Using defaults."
                )
                global_settings = GlobalMapConfig()

            # 2. Token Config (Profiles & ArUco Defaults)
            try:
                validated_tokens = TokenConfigSchema(**tokens_raw)

                # Sync Profiles
                if validated_tokens.token_profiles:
                    global_settings.token_profiles = {}
                    for name, prof_schema in validated_tokens.token_profiles.items():
                        prof = SizeProfile()
                        sync_pydantic_to_dataclass(prof_schema, prof)
                        global_settings.token_profiles[name] = prof
                else:
                    # Fallback defaults if no profiles loaded
                    global_settings.token_profiles = {
                        "small": SizeProfile(1, 15.0),
                        "medium": SizeProfile(1, 25.0),
                        "large": SizeProfile(2, 40.0),
                        "huge": SizeProfile(3, 60.0),
                    }

                # Sync ArUco Defaults
                global_settings.aruco_defaults = {}
                for aid, aruco_schema in validated_tokens.aruco_defaults.items():
                    aruco = ArucoDefinition(name=aruco_schema.name)
                    sync_pydantic_to_dataclass(aruco_schema, aruco)
                    global_settings.aruco_defaults[aid] = aruco

            except Exception as e:
                logging.warning(
                    f"MapConfig: Failed to validate token config: {e}. Using defaults."
                )
                # Keep factory defaults in global_settings

            global_settings.last_used_map = global_raw.get("last_used_map")

            # 3. Maps
            maps = {}
            raw_maps = raw.get("maps", {})
            for name, entry_data in raw_maps.items():
                try:
                    validated_entry = MapEntrySchema(**entry_data)
                    entry = MapEntry()
                    sync_pydantic_to_dataclass(validated_entry, entry)

                    # Manual sync for aruco_overrides (Dict[int, ArucoDefinition])
                    entry.aruco_overrides = {}
                    for aid, aruco_schema in validated_entry.aruco_overrides.items():
                        aruco = ArucoDefinition(name=aruco_schema.name)
                        sync_pydantic_to_dataclass(aruco_schema, aruco)
                        entry.aruco_overrides[aid] = aruco

                    maps[name] = entry
                except Exception as e:
                    logging.warning(
                        f"MapConfig: Failed to validate map entry for {name}: {e}"
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
            self.version = self._get_next_version()
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

    def get_map_grid_spacing(self, map_name: str) -> float:
        map_name = os.path.abspath(map_name)
        if map_name in self.data.maps:
            return self.data.maps[map_name].grid_spacing_svg
        return 0.0

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
        grid_type: GridType = GridType.SQUARE,
    ):
        map_name = os.path.abspath(map_name)
        if map_name not in self.data.maps:
            self.data.maps[map_name] = MapEntry()

        entry = self.data.maps[map_name]
        entry.grid_spacing_svg = grid_spacing_svg
        entry.grid_origin_svg_x = grid_origin_svg_x
        entry.grid_origin_svg_y = grid_origin_svg_y
        entry.grid_type = grid_type
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
        Returns {'calibrated': bool, 'has_session': bool, 'has_fow': bool}
        """
        filename = os.path.abspath(filename)
        entry = self.data.maps.get(filename)
        if not entry:
            return {"calibrated": False, "has_session": False, "has_fow": False}

        calibrated = entry.grid_spacing_svg > 0
        session_dir = None
        if self.storage:
            session_dir = os.path.join(self.storage.get_data_dir(), "sessions")
        has_session = SessionManager.has_session(filename, session_dir=session_dir)

        # Check for FoW
        fow_dir = self.get_fow_dir(filename)
        has_fow = os.path.exists(os.path.join(fow_dir, "fow.png"))

        return {
            "calibrated": calibrated,
            "has_session": has_session,
            "has_fow": has_fow,
        }

    def get_fow_dir(self, map_path: str) -> str:
        """Returns the stable storage directory for a map's Fog of War data."""
        abs_path = os.path.abspath(map_path)
        path_hash = hashlib.md5(abs_path.encode()).hexdigest()[:8]
        stem = os.path.splitext(os.path.basename(map_path))[0]
        # Store in managed data directory
        return os.path.join(self.storage.get_data_dir(), "fow", f"{stem}_{path_hash}")

    def load_fow_masks(self, map_path: str, fow_manager: "FogOfWarManager"):
        """Loads explored and visible masks into the manager."""
        storage_dir = self.get_fow_dir(map_path)
        if not os.path.exists(storage_dir):
            return

        # 1. Load Explored Mask
        fow_path = os.path.join(storage_dir, "fow.png")
        if os.path.exists(fow_path):
            try:
                img = cv2.imread(fow_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    if img.shape == (fow_manager.height, fow_manager.width):
                        fow_manager.explored_mask = img
                    else:
                        logging.warning(
                            "FoW dimension mismatch, ignoring: %s", fow_path
                        )
            except Exception as e:
                logging.error("Error loading FoW: %s", e)

        # 2. Load Visible Mask (LOS)
        los_path = os.path.join(storage_dir, "los.png")
        if os.path.exists(los_path):
            try:
                img = cv2.imread(los_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    if img.shape == (fow_manager.height, fow_manager.width):
                        fow_manager.visible_mask = img
                    else:
                        logging.warning(
                            "LOS dimension mismatch, ignoring: %s", los_path
                        )
            except Exception as e:
                logging.error("Error loading LOS: %s", e)

        # 3. Load Discovered Door IDs
        door_path = os.path.join(storage_dir, "discovered_doors.json")
        if os.path.exists(door_path):
            try:
                with open(door_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        fow_manager.discovered_door_ids = set(data)
            except Exception as e:
                logging.error(f"Error loading discovered doors: {e}")

    def save_fow_masks(self, map_path: str, fow_manager: "FogOfWarManager"):
        """Saves masks and discovered doors to stable storage."""
        storage_dir = self.get_fow_dir(map_path)
        try:
            os.makedirs(storage_dir, exist_ok=True)
            # Save Explored Mask
            cv2.imwrite(os.path.join(storage_dir, "fow.png"), fow_manager.explored_mask)
            # Save Visible Mask (LOS)
            cv2.imwrite(os.path.join(storage_dir, "los.png"), fow_manager.visible_mask)
            
            # Save Discovered Door IDs
            door_path = os.path.join(storage_dir, "discovered_doors.json")
            with open(door_path, "w") as f:
                json.dump(list(fow_manager.discovered_door_ids), f)
        except Exception as e:
            logging.error("Error saving FoW/LOS/Doors to %s: %s", storage_dir, e)

    # --- New ArUco / Profile Methods ---

    def set_token_profile(self, name: str, size: int, height_mm: float):
        """Helper to set a global token profile."""
        self.data.global_settings.token_profiles[name] = SizeProfile(
            size=size, height_mm=height_mm
        )
        self.save()

    def delete_token_profile(self, name: str):
        """Removes a global token profile."""
        if name in self.data.global_settings.token_profiles:
            del self.data.global_settings.token_profiles[name]
            self.save()

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
                height_mm=DEFAULT_TOKEN_HEIGHT_MM,
                is_known=False,
            )

        # 4. Resolve dimensions
        # Start with defaults
        size = 1
        height_mm = DEFAULT_TOKEN_HEIGHT_MM

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
            name=definition.name,
            type=definition.type,
            size=size,
            height_mm=height_mm,
            color=definition.color,
        )

    def set_global_aruco_definition(
        self,
        aruco_id: int,
        name: str,
        type: str = "NPC",
        profile: Optional[str] = None,
        size: Optional[int] = None,
        height_mm: Optional[float] = None,
        color: Optional[str] = None,
    ):
        """Helper to set a global definition. Enforces profile vs custom dimension exclusivity."""
        if profile:
            # Profile takes precedence: clear custom dimensions
            size = None
            height_mm = None
        elif size is not None or height_mm is not None:
            # Custom dimensions provided: clear profile
            profile = None

        self.data.global_settings.aruco_defaults[aruco_id] = ArucoDefinition(
            name=name,
            type=type,
            profile=profile,
            size=size,
            height_mm=height_mm,
            color=color,
        )
        self.save()

    def delete_global_aruco_definition(self, aruco_id: int):
        """Removes a global ArUco definition."""
        if aruco_id in self.data.global_settings.aruco_defaults:
            del self.data.global_settings.aruco_defaults[aruco_id]
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
        color: Optional[str] = None,
    ):
        """Helper to set a map override. Enforces profile vs custom dimension exclusivity."""
        map_name = os.path.abspath(map_name)
        if map_name not in self.data.maps:
            self.data.maps[map_name] = MapEntry()

        if profile:
            # Profile takes precedence: clear custom dimensions
            size = None
            height_mm = None
        elif size is not None or height_mm is not None:
            # Custom dimensions provided: clear profile
            profile = None

        self.data.maps[map_name].aruco_overrides[aruco_id] = ArucoDefinition(
            name=name,
            type=type,
            profile=profile,
            size=size,
            height_mm=height_mm,
            color=color,
        )
        self.save()

    def delete_map_aruco_override(self, map_name: str, aruco_id: int):
        """Removes a map-specific override, effectively resetting it to global default."""
        map_name = os.path.abspath(map_name)
        if map_name in self.data.maps:
            if aruco_id in self.data.maps[map_name].aruco_overrides:
                del self.data.maps[map_name].aruco_overrides[aruco_id]
                self.save()
