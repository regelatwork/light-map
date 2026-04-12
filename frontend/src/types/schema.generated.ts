/* tslint:disable */
/* eslint-disable */
/**
 * This file was automatically generated and should not be edited.
 * Run 'python3 scripts/generate_ts_schema.py' to update.
 */

export enum GmPosition {
  NONE = "None",
  NORTH = "North",
  SOUTH = "South",
  EAST = "East",
  WEST = "West",
  NORTH_WEST = "North West",
  NORTH_EAST = "North East",
  SOUTH_WEST = "South West",
  SOUTH_EAST = "South East",
}

export enum TokenDetectionAlgorithm {
  FLASH = "FLASH",
  STRUCTURED_LIGHT = "STRUCTURED_LIGHT",
  ARUCO = "ARUCO",
}

export enum NamingStyle {
  NUMBERED = "NUMBERED",
  AMERICAN = "AMERICAN",
  SCI_FI = "SCI_FI",
  FANTASY = "FANTASY",
}

export interface GlobalConfig {
  projector_ppi: number;
  flash_intensity: number;
  pointer_offset_mm: number;
  enable_hand_masking: boolean;
  enable_aruco_masking: boolean;
  aruco_mask_intensity: number;
  gm_position: GmPosition;
  use_projector_3d_model: boolean;
  inspection_linger_duration: number;
  door_thickness_multiplier: number;
  detection_algorithm: TokenDetectionAlgorithm;
  naming_style: NamingStyle;
  projector_pos_x_override?: number | null;
  projector_pos_y_override?: number | null;
  projector_pos_z_override?: number | null;
}


export interface FieldMetadata {
  title: string;
  description: string;
  min?: number;
  max?: number;
  step?: number;
  default?: any;
  options?: { label: string; value: string }[];
}

export const GLOBALCONFIG_METADATA: Record<keyof GlobalConfig, any> = {
  "projector_ppi": {
    "title": "Projector PPI",
    "description": "Pixels Per Inch of the projector at the projection surface.",
    "min": 10.0,
    "max": 1000.0,
    "default": 96.0
  },
  "flash_intensity": {
    "title": "Flash Intensity",
    "description": "Brightness of the calibration flash (0-255).",
    "min": 0,
    "max": 255,
    "default": 255
  },
  "pointer_offset_mm": {
    "title": "Pointer Offset (mm)",
    "description": "Distance the virtual cursor extends beyond your fingertip.",
    "min": 0.0,
    "max": 500.0,
    "default": 50.8
  },
  "enable_hand_masking": {
    "title": "Enable Hand Masking",
    "description": "Hide the projection under the user's hands to prevent interference.",
    "default": false
  },
  "enable_aruco_masking": {
    "title": "Enable ArUco Masking",
    "description": "Hide the projection under detected ArUco markers.",
    "default": true
  },
  "aruco_mask_intensity": {
    "title": "ArUco Mask Intensity",
    "description": "Brightness level of the ArUco masks (0=Black, 255=White).",
    "min": 0,
    "max": 255,
    "default": 0
  },
  "gm_position": {
    "title": "GM Position",
    "description": "Location of the GM relative to the table.",
    "default": "None",
    "options": [
      {
        "label": "None",
        "value": "None"
      },
      {
        "label": "North",
        "value": "North"
      },
      {
        "label": "South",
        "value": "South"
      },
      {
        "label": "East",
        "value": "East"
      },
      {
        "label": "West",
        "value": "West"
      },
      {
        "label": "North West",
        "value": "North West"
      },
      {
        "label": "North East",
        "value": "North East"
      },
      {
        "label": "South West",
        "value": "South West"
      },
      {
        "label": "South East",
        "value": "South East"
      }
    ]
  },
  "use_projector_3d_model": {
    "title": "Use Projector 3D Model",
    "description": "Enable advanced distortion correction using the projector's physical position.",
    "default": true
  },
  "inspection_linger_duration": {
    "title": "Inspection Linger (s)",
    "description": "How long token details stay visible after the hand is removed.",
    "min": 0.0,
    "max": 60.0,
    "default": 10.0
  },
  "door_thickness_multiplier": {
    "title": "Door Thickness Multiplier",
    "description": "Adjusts the visual thickness of doors on the map.",
    "min": 1.0,
    "max": 10.0,
    "default": 3.0
  },
  "detection_algorithm": {
    "title": "Detection Algorithm",
    "description": "Algorithm used for physical token detection.",
    "default": "FLASH",
    "options": [
      {
        "label": "Flash",
        "value": "FLASH"
      },
      {
        "label": "Structured Light",
        "value": "STRUCTURED_LIGHT"
      },
      {
        "label": "Aruco",
        "value": "ARUCO"
      }
    ]
  },
  "naming_style": {
    "title": "Naming Style",
    "description": "Aesthetic style for automatically generated token names.",
    "default": "SCI_FI",
    "options": [
      {
        "label": "Numbered",
        "value": "NUMBERED"
      },
      {
        "label": "American",
        "value": "AMERICAN"
      },
      {
        "label": "Sci Fi",
        "value": "SCI_FI"
      },
      {
        "label": "Fantasy",
        "value": "FANTASY"
      }
    ]
  },
  "projector_pos_x_override": {
    "title": "Projector X Override",
    "description": "Manually override the projector's X position (mm)."
  },
  "projector_pos_y_override": {
    "title": "Projector Y Override",
    "description": "Manually override the projector's Y position (mm)."
  },
  "projector_pos_z_override": {
    "title": "Projector Z Override",
    "description": "Manually override the projector's Z position (mm)."
  }
};
