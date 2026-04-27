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

export enum GridType {
  SQUARE = "SQUARE",
  HEX_POINTY = "HEX_POINTY",
  HEX_FLAT = "HEX_FLAT",
}

export interface SizeProfile {
  size: number;
  height_mm: number;
}

export interface ArucoDefinition {
  name: string;
  type: string;
  profile?: string | null;
  size?: number | null;
  height_mm?: number | null;
  color?: string | null;
}

export interface TokenConfig {
  token_profiles: Record<string, SizeProfile>;
  aruco_defaults: Record<number, ArucoDefinition>;
}

export interface ViewportState {
  x: number;
  y: number;
  zoom: number;
  rotation: number;
}

export interface Token {
  id: number;
  world_x: number;
  world_y: number;
  world_z: number;
  marker_x?: number | null;
  marker_y?: number | null;
  marker_z: number;
  grid_x?: number | null;
  grid_y?: number | null;
  screen_x?: number | null;
  screen_y?: number | null;
  confidence: number;
  is_occluded: boolean;
  is_duplicate: boolean;
  name?: string | null;
  color?: string | null;
  type: string;
  profile?: string | null;
  size?: number | null;
  height_mm?: number | null;
}

export interface SessionData {
  map_file: string;
  viewport: ViewportState;
  tokens: Token[];
  door_states: Record<string, boolean>;
  timestamp: string;
}

export interface MapEntry {
  scale_factor: number;
  viewport: ViewportState;
  grid_spacing_svg: number;
  grid_origin_svg_x: number;
  grid_origin_svg_y: number;
  grid_type: GridType;
  physical_unit_inches: number;
  scale_factor_1to1: number;
  last_seen: string;
  aruco_overrides: Record<number, ArucoDefinition>;
  fow_disabled: boolean;
  grid_overlay_visible: boolean;
  grid_overlay_color: string;
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

export interface WedgeSegment {
  start_idx: number;
  end_idx: number;
  status: number;
}

export interface CoverResult {
  ac_bonus: number;
  reflex_bonus: number;
  best_apex: [number, number];
  segments: WedgeSegment[];
  npc_pixels: [number, number][];
  total_ratio: number;
  wall_ratio: number;
  soft_ratio: number;
  explanation: string;
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

export const SIZEPROFILE_METADATA: Record<keyof SizeProfile, FieldMetadata> = {
  "size": {
    "title": "Size",
    "description": "Size in grid units.",
    "min": 1,
    "max": 10,
    "default": 1
  },
  "height_mm": {
    "title": "Height (mm)",
    "description": "Physical height of the token in millimeters.",
    "min": 0.0,
    "max": 500.0,
    "default": 50.0
  }
};

export const ARUCODEFINITION_METADATA: Record<keyof ArucoDefinition, FieldMetadata> = {
  "name": {
    "title": "Name",
    "description": "Display name for this ArUco marker."
  },
  "type": {
    "title": "Type",
    "description": "Token type (e.g., PC, NPC, Enemy).",
    "default": "NPC"
  },
  "profile": {
    "title": "Profile",
    "description": "Reference to a SizeProfileSchema by name."
  },
  "size": {
    "title": "Custom Size",
    "description": "Override size in grid units.",
    "min": 1,
    "max": 10
  },
  "height_mm": {
    "title": "Custom Height (mm)",
    "description": "Override physical height in mm.",
    "min": 0.0,
    "max": 500.0
  },
  "color": {
    "title": "Color",
    "description": "CSS color override for the token."
  }
};

export const TOKENCONFIG_METADATA: Record<keyof TokenConfig, FieldMetadata> = {
  "token_profiles": {
    "title": "Token Profiles",
    "description": "Named size and height presets."
  },
  "aruco_defaults": {
    "title": "ArUco Defaults",
    "description": "Global default settings for specific ArUco IDs."
  }
};

export const VIEWPORTSTATE_METADATA: Record<keyof ViewportState, FieldMetadata> = {
  "x": {
    "title": "X Offset",
    "description": "Horizontal pan offset in SVG units.",
    "default": 0.0
  },
  "y": {
    "title": "Y Offset",
    "description": "Vertical pan offset in SVG units.",
    "default": 0.0
  },
  "zoom": {
    "title": "Zoom",
    "description": "Zoom level (1.0 = 100%).",
    "default": 1.0
  },
  "rotation": {
    "title": "Rotation",
    "description": "Rotation in degrees.",
    "default": 0.0
  }
};

export const TOKEN_METADATA: Record<keyof Token, FieldMetadata> = {
  "id": {
    "title": "ID",
    "description": "Unique identifier (e.g., ArUco ID)."
  },
  "world_x": {
    "title": "World X",
    "description": "Horizontal position in world coordinates."
  },
  "world_y": {
    "title": "World Y",
    "description": "Vertical position in world coordinates."
  },
  "world_z": {
    "title": "World Z",
    "description": "Height above the map surface.",
    "default": 0.0
  },
  "marker_x": {
    "title": "Marker X",
    "description": "Horizontal marker position at its actual height."
  },
  "marker_y": {
    "title": "Marker Y",
    "description": "Vertical marker position at its actual height."
  },
  "marker_z": {
    "title": "Marker Z",
    "description": "Physical height of the marker.",
    "default": 0.0
  },
  "grid_x": {
    "title": "Grid X",
    "description": "Snapped horizontal grid coordinate."
  },
  "grid_y": {
    "title": "Grid Y",
    "description": "Snapped vertical grid coordinate."
  },
  "screen_x": {
    "title": "Screen X",
    "description": "Horizontal projector pixel position."
  },
  "screen_y": {
    "title": "Screen Y",
    "description": "Vertical projector pixel position."
  },
  "confidence": {
    "title": "Confidence",
    "description": "Detection confidence (0.0 to 1.0).",
    "default": 1.0
  },
  "is_occluded": {
    "title": "Is Occluded",
    "description": "True if the token is currently hidden.",
    "default": false
  },
  "is_duplicate": {
    "title": "Is Duplicate",
    "description": "True if this is a ghost detection.",
    "default": false
  },
  "name": {
    "title": "Name",
    "description": "Assigned name of the token."
  },
  "color": {
    "title": "Color",
    "description": "Assigned color for the token ring."
  },
  "type": {
    "title": "Type",
    "description": "Token type (e.g., PC, NPC).",
    "default": "NPC"
  },
  "profile": {
    "title": "Profile",
    "description": "The size profile name used."
  },
  "size": {
    "title": "Size",
    "description": "Resolved size in grid units."
  },
  "height_mm": {
    "title": "Height (mm)",
    "description": "Resolved height in mm."
  }
};

export const SESSIONDATA_METADATA: Record<keyof SessionData, FieldMetadata> = {
  "map_file": {
    "title": "Map File",
    "description": "Absolute path to the map image."
  },
  "viewport": {
    "title": "Viewport",
    "description": "Saved pan and zoom state."
  },
  "tokens": {
    "title": "Tokens",
    "description": "List of active tokens."
  },
  "door_states": {
    "title": "Door States",
    "description": "Map of door IDs to their open/closed status."
  },
  "timestamp": {
    "title": "Timestamp",
    "description": "ISO 8601 creation time.",
    "default": ""
  }
};

export const MAPENTRY_METADATA: Record<keyof MapEntry, FieldMetadata> = {
  "scale_factor": {
    "title": "Scale Factor",
    "description": "Global zoom multiplier for this map.",
    "default": 1.0
  },
  "viewport": {
    "title": "Viewport",
    "description": "Saved viewport state."
  },
  "grid_spacing_svg": {
    "title": "Grid Spacing",
    "description": "Size of one grid cell in SVG units.",
    "default": 0.0
  },
  "grid_origin_svg_x": {
    "title": "Grid Origin X",
    "description": "Horizontal grid offset.",
    "default": 0.0
  },
  "grid_origin_svg_y": {
    "title": "Grid Origin Y",
    "description": "Vertical grid offset.",
    "default": 0.0
  },
  "grid_type": {
    "title": "Grid Type",
    "description": "Grid geometry (Square or Hex).",
    "default": "SQUARE",
    "options": [
      {
        "label": "Square",
        "value": "SQUARE"
      },
      {
        "label": "Hex Pointy",
        "value": "HEX_POINTY"
      },
      {
        "label": "Hex Flat",
        "value": "HEX_FLAT"
      }
    ]
  },
  "physical_unit_inches": {
    "title": "Physical Unit",
    "description": "Size of one grid cell in inches.",
    "default": 1.0
  },
  "scale_factor_1to1": {
    "title": "1:1 Scale Factor",
    "description": "Zoom level required for physical 1:1 scale.",
    "default": 1.0
  },
  "last_seen": {
    "title": "Last Seen",
    "description": "ISO 8601 timestamp of last usage.",
    "default": ""
  },
  "aruco_overrides": {
    "title": "ArUco Overrides",
    "description": "Map-specific marker definitions."
  },
  "fow_disabled": {
    "title": "Disable Fog of War",
    "description": "If true, the entire map is always visible.",
    "default": false
  },
  "grid_overlay_visible": {
    "title": "Grid Overlay Visible",
    "description": "If true, a grid will be rendered over the map.",
    "default": false
  },
  "grid_overlay_color": {
    "title": "Grid Overlay Color",
    "description": "CSS color for the grid lines.",
    "default": "rgba(255, 255, 255, 0.5)"
  }
};

export const GLOBALCONFIG_METADATA: Record<keyof GlobalConfig, FieldMetadata> = {
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

export const WEDGESEGMENT_METADATA: Record<keyof WedgeSegment, FieldMetadata> = {
  "start_idx": {
    "title": "Start Index",
    "description": ""
  },
  "end_idx": {
    "title": "End Index",
    "description": ""
  },
  "status": {
    "title": "Status",
    "description": ""
  }
};

export const COVERRESULT_METADATA: Record<keyof CoverResult, FieldMetadata> = {
  "ac_bonus": {
    "title": "AC Bonus",
    "description": ""
  },
  "reflex_bonus": {
    "title": "Reflex Bonus",
    "description": ""
  },
  "best_apex": {
    "title": "Best Apex",
    "description": ""
  },
  "segments": {
    "title": "Segments",
    "description": ""
  },
  "npc_pixels": {
    "title": "NPC Pixels",
    "description": ""
  },
  "total_ratio": {
    "title": "Total Ratio",
    "description": "",
    "default": 0.0
  },
  "wall_ratio": {
    "title": "Wall Ratio",
    "description": "",
    "default": 0.0
  },
  "soft_ratio": {
    "title": "Soft Ratio",
    "description": "",
    "default": 0.0
  },
  "explanation": {
    "title": "Explanation",
    "description": "",
    "default": ""
  }
};
