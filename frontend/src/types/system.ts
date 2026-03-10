export interface VisibilityBlocker {
  id: number;
  type: string;
  is_open: boolean;
  points: [number, number][];
}

export interface WorldState {
  scene: string;
  fps: number;
  blockers?: VisibilityBlocker[];
  [key: string]: unknown;
}

export interface Token {
  id: number;
  world_x: number;
  world_y: number;
  [key: string]: unknown;
}

export interface SystemConfig {
  cam_res: [number, number];
  proj_res: [number, number];
  enable_hand_masking: boolean;
  gm_position: string;
  debug_mode: boolean;
  fow_disabled: boolean;
  current_map_path?: string;
  map_width?: number;
  map_height?: number;
  [key: string]: unknown;
}

export interface SystemState {
  world: WorldState;
  tokens: Token[];
  menu: Record<string, unknown> | null;
  config: SystemConfig;
  timestamp: number;
  isConnected: boolean;
  error: string | null;
  grid_spacing_svg: number;
  grid_origin_svg_x: number;
  grid_origin_svg_y: number;
}

export const INITIAL_STATE: SystemState = {
  world: { scene: 'LOADING', fps: 0 },
  tokens: [],
  menu: null,
  config: {
    cam_res: [0, 0],
    proj_res: [0, 0],
    enable_hand_masking: false,
    gm_position: 'None',
    debug_mode: false,
    fow_disabled: false,
  },
  timestamp: 0,
  isConnected: false,
  error: null,
  grid_spacing_svg: 0,
  grid_origin_svg_x: 0,
  grid_origin_svg_y: 0,
};
