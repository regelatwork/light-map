/**
 * NOTE: Enums in this file are mirrored from the Python backend
 * (src/light_map/common_types.py and visibility_types.py).
 *
 * Changes here MUST be kept in sync with the backend.
 * This is enforced by the backend test: tests/test_enum_sync.py
 */

export enum VisibilityType {
  WALL = 'wall',
  DOOR = 'door',
  WINDOW = 'window',
}

export enum ResultType {
  ARUCO = 'ARUCO',
  HANDS = 'HANDS',
  GESTURE = 'GESTURE',
  ACTION = 'ACTION',
}

export enum GestureType {
  OPEN_PALM = 'Open Palm',
  CLOSED_FIST = 'Closed Fist',
  GUN = 'Gun',
  POINTING = 'Pointing',
  VICTORY = 'Victory',
  ROCK = 'Rock',
  SHAKA = 'Shaka',
  UNKNOWN = 'Unknown',
  NONE = 'None',
}

export enum SceneId {
  MENU = 'MENU',
  VIEWING = 'VIEWING',
  MAP = 'MAP',
  SCANNING = 'SCANNING',
  CALIBRATE_FLASH = 'CALIBRATE_FLASH',
  CALIBRATE_PPI = 'CALIBRATE_PPI',
  CALIBRATE_MAP_GRID = 'CALIBRATE_MAP_GRID',
  CALIBRATE_INTRINSICS = 'CALIBRATE_INTRINSICS',
  CALIBRATE_PROJECTOR = 'CALIBRATE_PROJECTOR',
  CALIBRATE_EXTRINSICS = 'CALIBRATE_EXTRINSICS',
  CALIBRATE_PROJECTOR_3D = 'CALIBRATE_PROJECTOR_3D',
  EXCLUSIVE_VISION = 'EXCLUSIVE_VISION',
}

export enum SelectionType {
  NONE = 'NONE',
  DOOR = 'DOOR',
  TOKEN = 'TOKEN',
}

export enum MenuActions {
  TOGGLE_DEBUG_MODE = 'TOGGLE_DEBUG_MODE',
  TOGGLE_DEBUG = 'TOGGLE_DEBUG',
  EXIT = 'EXIT',
  CLOSE_MENU = 'CLOSE_MENU',
  CALIBRATE = 'CALIBRATE',
  CALIBRATE_INTRINSICS = 'CALIBRATE_INTRINSICS',
  CALIBRATE_PROJECTOR = 'CALIBRATE_PROJECTOR',
  CALIBRATE_PPI = 'CALIBRATE_PPI',
  CALIBRATE_EXTRINSICS = 'CALIBRATE_EXTRINSICS',
  CALIBRATE_PROJECTOR_3D = 'CALIBRATE_PROJECTOR_3D',
  NAV_BACK = 'NAV_BACK',
  MAP_CONTROLS = 'MAP_CONTROLS',
  ROTATE_CW = 'ROTATE_CW',
  ROTATE_CCW = 'ROTATE_CCW',
  RESET_VIEW = 'RESET_VIEW',
  CALIBRATE_SCALE = 'CALIBRATE_SCALE',
  SET_MAP_SCALE = 'SET_MAP_SCALE',
  RESET_ZOOM = 'RESET_ZOOM',
  UNDO_NAV = 'UNDO_NAV',
  REDO_NAV = 'REDO_NAV',
  PAGE_NEXT = 'PAGE_NEXT',
  PAGE_PREV = 'PAGE_PREV',
  SCAN_SESSION = 'SCAN_SESSION',
  LOAD_SESSION = 'LOAD_SESSION',
  CALIBRATE_FLASH = 'CALIBRATE_FLASH',
  SCAN_ALGORITHM = 'SCAN_ALGORITHM',
  TOGGLE_HAND_MASKING = 'TOGGLE_HAND_MASKING',
  TOGGLE_ARUCO_MASKING = 'TOGGLE_ARUCO_MASKING',
  SET_GM_POSITION = 'SET_GM_POSITION',
  SYNC_VISION = 'SYNC_VISION',
  RESET_FOW = 'RESET_FOW',
  TOGGLE_FOW = 'TOGGLE_FOW',
  TOGGLE_DOOR = 'TOGGLE_DOOR',
  TOGGLE_TOKENS = 'TOGGLE_TOKENS',
}

export enum GmPosition {
  NONE = 'None',
  NORTH = 'North',
  SOUTH = 'South',
  EAST = 'East',
  WEST = 'West',
  NORTH_WEST = 'North West',
  NORTH_EAST = 'North East',
  SOUTH_WEST = 'South West',
  SOUTH_EAST = 'South East',
}

export interface VisibilityBlocker {
  id: string;
  type: VisibilityType;
  is_open: boolean;
  points: [number, number][];
}

export interface ViewportState {
  x: number;
  y: number;
  zoom: number;
  rotation: number;
}

export interface WorldState {
  scene: SceneId | string;
  fps: number;
  viewport?: ViewportState;
  blockers?: VisibilityBlocker[];
  [key: string]: unknown;
}

export interface Token {
  id: number;
  world_x: number;
  world_y: number;
  name?: string;
  color?: string;
  type?: string;
  profile?: string;
  size?: number;
  height_mm?: number;
  [key: string]: unknown;
}

export interface TokenProfile {
  size: number;
  height_mm: number;
}

export interface ArucoDefault {
  name: string;
  type: string;
  profile?: string;
  size?: number;
  height_mm?: number;
  color?: string;
}

export interface SystemConfig {
  cam_res: [number, number];
  proj_res: [number, number];
  enable_hand_masking: boolean;
  enable_aruco_masking: boolean;
  gm_position: GmPosition;
  debug_mode: boolean;
  fow_disabled: boolean;
  use_projector_3d_model: boolean;
  calibrated_projector_pos?: [number, number, number] | null;
  current_projector_pos?: [number, number, number];
  current_map_path?: string;
  map_width?: number;
  map_height?: number;
  token_profiles?: Record<string, TokenProfile>;
  aruco_defaults?: Record<number, ArucoDefault>;
  [key: string]: unknown;
}

export interface MenuState {
  title: string;
  items: string[];
  depth?: number;
}

export interface MapInfo {
  name: string;
  aruco_overrides?: Record<number, ArucoDefault>;
}

export interface SystemState {
  world: WorldState;
  tokens: Token[];
  menu: MenuState | null;
  config: SystemConfig;
  maps: Record<string, MapInfo>;
  timestamp: number;
  isConnected: boolean;
  error: string | null;
  grid_spacing_svg: number;
  grid_origin_svg_x: number;
  grid_origin_svg_y: number;
  map_timestamp: number;
  menu_timestamp: number;
  tokens_timestamp: number;
  raw_aruco_timestamp: number;
  hands_timestamp: number;
  scene_timestamp: number;
  notifications_timestamp: number;
  viewport_timestamp: number;
  visibility_timestamp: number;
  fow_timestamp: number;
}

export const INITIAL_STATE: SystemState = {
  world: { scene: 'MenuScene', fps: 0 },
  tokens: [],
  menu: null,
  config: {
    cam_res: [0, 0],
    proj_res: [0, 0],
    enable_hand_masking: false,
    enable_aruco_masking: true,
    gm_position: GmPosition.NONE,
    debug_mode: false,
    fow_disabled: false,
    use_projector_3d_model: true,
  },
  maps: {},
  timestamp: 0,
  isConnected: false,
  error: null,
  grid_spacing_svg: 0,
  grid_origin_svg_x: 0,
  grid_origin_svg_y: 0,
  map_timestamp: 0,
  menu_timestamp: 0,
  tokens_timestamp: 0,
  raw_aruco_timestamp: 0,
  hands_timestamp: 0,
  scene_timestamp: 0,
  notifications_timestamp: 0,
  viewport_timestamp: 0,
  visibility_timestamp: 0,
  fow_timestamp: 0,
};
