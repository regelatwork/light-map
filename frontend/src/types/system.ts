export interface WorldState {
  scene: string;
  fps: number;
  [key: string]: any;
}

export interface Token {
  id: number;
  world_x: number;
  world_y: number;
  [key: string]: any;
}

export interface SystemState {
  world: WorldState;
  tokens: Token[];
  menu: any;
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
  menu: {},
  timestamp: 0,
  isConnected: false,
  error: null,
  grid_spacing_svg: 0,
  grid_origin_svg_x: 0,
  grid_origin_svg_y: 0,
};
