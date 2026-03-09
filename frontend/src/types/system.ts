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
}

export const INITIAL_STATE: SystemState = {
  world: { scene: 'LOADING', fps: 0 },
  tokens: [],
  menu: {},
  timestamp: 0,
  isConnected: false,
  error: null,
};
