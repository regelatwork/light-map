"""
Configuration Schema: Single Source of Truth (SSOT)

This file defines the configuration models for the entire project. All configuration settings,
default values, user-facing labels, and descriptions MUST be defined here using Pydantic models.

Workflow Invariants:
1.  **Schema-First**: Define all new settings here first.
2.  **Field Metadata**: Use Pydantic's `Field` to define 'title', 'description', and constraints (e.g., 'ge', 'le').
3.  **Frontend Sync**: After any change to this file, you MUST run the generation script:
    `python3 scripts/generate_ts_schema.py`
4.  **Static Checking**: The frontend build and `tests/test_config_sync.py` will fail if the frontend
    types are not synchronized with this file.

Architecture:
- Backend: These Pydantic models are used for API validation and storage serialization.
- Frontend: The generator script produces TypeScript interfaces and a metadata registry.
- UI: Generic components in `frontend/src/components/common/ConfigInputs.tsx` use this metadata.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from enum import StrEnum


class GmPosition(StrEnum):
    NONE = "None"
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    NORTH_WEST = "North West"
    NORTH_EAST = "North East"
    SOUTH_WEST = "South West"
    SOUTH_EAST = "South East"


class TokenDetectionAlgorithm(StrEnum):
    FLASH = "FLASH"
    STRUCTURED_LIGHT = "STRUCTURED_LIGHT"
    ARUCO = "ARUCO"


class NamingStyle(StrEnum):
    NUMBERED = "NUMBERED"
    AMERICAN = "AMERICAN"
    SCI_FI = "SCI_FI"
    FANTASY = "FANTASY"


class GridType(StrEnum):
    SQUARE = "SQUARE"
    HEX_POINTY = "HEX_POINTY"
    HEX_FLAT = "HEX_FLAT"


class SizeProfileSchema(BaseModel):
    size: int = Field(
        default=1, ge=1, le=10, title="Size", description="Size in grid units."
    )
    height_mm: float = Field(
        default=50.0,
        ge=0.0,
        le=500.0,
        title="Height (mm)",
        description="Physical height of the token in millimeters.",
    )


class ArucoDefinitionSchema(BaseModel):
    name: str = Field(
        ..., title="Name", description="Display name for this ArUco marker."
    )
    type: str = Field(
        default="NPC", title="Type", description="Token type (e.g., PC, NPC, Enemy)."
    )
    profile: Optional[str] = Field(
        default=None,
        title="Profile",
        description="Reference to a SizeProfileSchema by name.",
    )
    size: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        title="Custom Size",
        description="Override size in grid units.",
    )
    height_mm: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=500.0,
        title="Custom Height (mm)",
        description="Override physical height in mm.",
    )
    color: Optional[str] = Field(
        default=None, title="Color", description="CSS color override for the token."
    )


class TokenConfigSchema(BaseModel):
    token_profiles: Dict[str, SizeProfileSchema] = Field(
        default_factory=dict,
        title="Token Profiles",
        description="Named size and height presets.",
    )
    aruco_defaults: Dict[int, ArucoDefinitionSchema] = Field(
        default_factory=dict,
        title="ArUco Defaults",
        description="Global default settings for specific ArUco IDs.",
    )


class ViewportStateSchema(BaseModel):
    x: float = Field(
        default=0.0, title="X Offset", description="Horizontal pan offset in SVG units."
    )
    y: float = Field(
        default=0.0, title="Y Offset", description="Vertical pan offset in SVG units."
    )
    zoom: float = Field(
        default=1.0, title="Zoom", description="Zoom level (1.0 = 100%)."
    )
    rotation: float = Field(
        default=0.0, title="Rotation", description="Rotation in degrees."
    )


class TokenSchema(BaseModel):
    id: int = Field(..., title="ID", description="Unique identifier (e.g., ArUco ID).")
    world_x: float = Field(
        ..., title="World X", description="Horizontal position in world coordinates."
    )
    world_y: float = Field(
        ..., title="World Y", description="Vertical position in world coordinates."
    )
    world_z: float = Field(
        default=0.0, title="World Z", description="Height above the map surface."
    )
    marker_x: Optional[float] = Field(
        default=None,
        title="Marker X",
        description="Horizontal marker position at its actual height.",
    )
    marker_y: Optional[float] = Field(
        default=None,
        title="Marker Y",
        description="Vertical marker position at its actual height.",
    )
    marker_z: float = Field(
        default=0.0, title="Marker Z", description="Physical height of the marker."
    )
    grid_x: Optional[int] = Field(
        default=None, title="Grid X", description="Snapped horizontal grid coordinate."
    )
    grid_y: Optional[int] = Field(
        default=None, title="Grid Y", description="Snapped vertical grid coordinate."
    )
    screen_x: Optional[float] = Field(
        default=None,
        title="Screen X",
        description="Horizontal projector pixel position.",
    )
    screen_y: Optional[float] = Field(
        default=None, title="Screen Y", description="Vertical projector pixel position."
    )
    confidence: float = Field(
        default=1.0,
        title="Confidence",
        description="Detection confidence (0.0 to 1.0).",
    )
    is_occluded: bool = Field(
        default=False,
        title="Is Occluded",
        description="True if the token is currently hidden.",
    )
    is_duplicate: bool = Field(
        default=False,
        title="Is Duplicate",
        description="True if this is a ghost detection.",
    )
    name: Optional[str] = Field(
        default=None, title="Name", description="Assigned name of the token."
    )
    color: Optional[str] = Field(
        default=None, title="Color", description="Assigned color for the token ring."
    )
    type: str = Field(
        default="NPC", title="Type", description="Token type (e.g., PC, NPC)."
    )
    profile: Optional[str] = Field(
        default=None, title="Profile", description="The size profile name used."
    )
    size: Optional[int] = Field(
        default=None, title="Size", description="Resolved size in grid units."
    )
    height_mm: Optional[float] = Field(
        default=None, title="Height (mm)", description="Resolved height in mm."
    )


class SessionDataSchema(BaseModel):
    map_file: str = Field(
        ..., title="Map File", description="Absolute path to the map image."
    )
    viewport: ViewportStateSchema = Field(
        ..., title="Viewport", description="Saved pan and zoom state."
    )
    tokens: List[TokenSchema] = Field(
        default_factory=list, title="Tokens", description="List of active tokens."
    )
    door_states: Dict[str, bool] = Field(
        default_factory=dict,
        title="Door States",
        description="Map of door IDs to their open/closed status.",
    )
    timestamp: str = Field(
        default="", title="Timestamp", description="ISO 8601 creation time."
    )


class MapEntrySchema(BaseModel):
    scale_factor: float = Field(
        default=1.0,
        title="Scale Factor",
        description="Global zoom multiplier for this map.",
    )
    viewport: ViewportStateSchema = Field(
        default_factory=ViewportStateSchema,
        title="Viewport",
        description="Saved viewport state.",
    )
    grid_spacing_svg: float = Field(
        default=0.0,
        title="Grid Spacing",
        description="Size of one grid cell in SVG units.",
    )
    grid_origin_svg_x: float = Field(
        default=0.0, title="Grid Origin X", description="Horizontal grid offset."
    )
    grid_origin_svg_y: float = Field(
        default=0.0, title="Grid Origin Y", description="Vertical grid offset."
    )
    grid_type: GridType = Field(
        default=GridType.SQUARE, title="Grid Type", description="Grid geometry (Square or Hex)."
    )
    physical_unit_inches: float = Field(
        default=1.0,
        title="Physical Unit",
        description="Size of one grid cell in inches.",
    )
    scale_factor_1to1: float = Field(
        default=1.0,
        title="1:1 Scale Factor",
        description="Zoom level required for physical 1:1 scale.",
    )
    last_seen: str = Field(
        default="", title="Last Seen", description="ISO 8601 timestamp of last usage."
    )
    aruco_overrides: Dict[int, ArucoDefinitionSchema] = Field(
        default_factory=dict,
        title="ArUco Overrides",
        description="Map-specific marker definitions.",
    )
    fow_disabled: bool = Field(
        default=False,
        title="Disable Fog of War",
        description="If true, the entire map is always visible.",
    )


class GlobalConfigSchema(BaseModel):
    projector_ppi: float = Field(
        default=96.0,
        ge=10.0,
        le=1000.0,
        title="Projector PPI",
        description="Pixels Per Inch of the projector at the projection surface.",
    )
    flash_intensity: int = Field(
        default=255,
        ge=0,
        le=255,
        title="Flash Intensity",
        description="Brightness of the calibration flash (0-255).",
    )
    pointer_offset_mm: float = Field(
        default=50.8,
        ge=0.0,
        le=500.0,
        title="Pointer Offset (mm)",
        description="Distance the virtual cursor extends beyond your fingertip.",
    )
    enable_hand_masking: bool = Field(
        default=False,
        title="Enable Hand Masking",
        description="Hide the projection under the user's hands to prevent interference.",
    )
    enable_aruco_masking: bool = Field(
        default=True,
        title="Enable ArUco Masking",
        description="Hide the projection under detected ArUco markers.",
    )
    aruco_mask_intensity: int = Field(
        default=0,
        ge=0,
        le=255,
        title="ArUco Mask Intensity",
        description="Brightness level of the ArUco masks (0=Black, 255=White).",
    )
    gm_position: GmPosition = Field(
        default=GmPosition.NONE,
        title="GM Position",
        description="Location of the GM relative to the table.",
    )
    use_projector_3d_model: bool = Field(
        default=True,
        title="Use Projector 3D Model",
        description="Enable advanced distortion correction using the projector's physical position.",
    )
    inspection_linger_duration: float = Field(
        default=10.0,
        ge=0.0,
        le=60.0,
        title="Inspection Linger (s)",
        description="How long token details stay visible after the hand is removed.",
    )
    door_thickness_multiplier: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        title="Door Thickness Multiplier",
        description="Adjusts the visual thickness of doors on the map.",
    )
    detection_algorithm: TokenDetectionAlgorithm = Field(
        default=TokenDetectionAlgorithm.FLASH,
        title="Detection Algorithm",
        description="Algorithm used for physical token detection.",
    )
    naming_style: NamingStyle = Field(
        default=NamingStyle.SCI_FI,
        title="Naming Style",
        description="Aesthetic style for automatically generated token names.",
    )
    projector_pos_x_override: Optional[float] = Field(
        default=None,
        title="Projector X Override",
        description="Manually override the projector's X position (mm).",
    )
    projector_pos_y_override: Optional[float] = Field(
        default=None,
        title="Projector Y Override",
        description="Manually override the projector's Y position (mm).",
    )
    projector_pos_z_override: Optional[float] = Field(
        default=None,
        title="Projector Z Override",
        description="Manually override the projector's Z position (mm).",
    )
