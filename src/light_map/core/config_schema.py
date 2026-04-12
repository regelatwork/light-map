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
from typing import Optional
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
