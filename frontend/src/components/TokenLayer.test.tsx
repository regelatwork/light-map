import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TokenLayer } from './TokenLayer';
import { SelectionProvider } from './SelectionContext';
import { type Token } from '../types/system';

// Mock useSystemState hook
vi.mock('../hooks/useSystemState', () => ({
  useSystemState: vi.fn(),
  INITIAL_STATE: {
    world: { scene: 'MenuScene', fps: 0 },
    tokens: [],
    menu: null,
    config: {
      cam_res: [0, 0],
      proj_res: [0, 0],
      enable_hand_masking: false,
      enable_aruco_masking: true,
      gm_position: 'None',
      debug_mode: false,
      fow_disabled: false,
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
  },
}));

import { useSystemState, INITIAL_STATE } from '../hooks/useSystemState';

describe('TokenLayer', () => {
  it('renders NPC as a rect and PC as a circle', () => {
    vi.mocked(useSystemState).mockReturnValue({
      ...INITIAL_STATE,
      isConnected: true,
      tokens: [
        { id: 1, world_x: 100, world_y: 100, type: 'NPC', name: 'Goblin' } as unknown as Token,
        { id: 2, world_x: 200, world_y: 200, type: 'PC', name: 'Hero' } as unknown as Token,
      ],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_spacing_svg: 50,
    });

    const { container } = render(
      <SelectionProvider>
        <svg>
          <TokenLayer />
        </svg>
      </SelectionProvider>
    );

    // NPC (id: 1) should be a rect
    const rects = container.querySelectorAll('rect');
    expect(rects.length).toBe(1);
    expect(rects[0]).toHaveAttribute('x', '-15');
    expect(rects[0]).toHaveAttribute('width', '30');

    // PC (id: 2) should be a circle
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(1);
    expect(circles[0]).toHaveAttribute('r', '15');

    // Check labels
    expect(container.textContent).toContain('Goblin');
    expect(container.textContent).toContain('Hero');
  });

  it('renders PC as circle if type is missing', () => {
    vi.mocked(useSystemState).mockReturnValue({
      ...INITIAL_STATE,
      isConnected: true,
      tokens: [
        { id: 3, world_x: 300, world_y: 300 } as unknown as Token, // type missing
      ],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_spacing_svg: 50,
    });

    const { container } = render(
      <SelectionProvider>
        <svg>
          <TokenLayer />
        </svg>
      </SelectionProvider>
    );

    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(1);
    expect(circles[0]).toHaveAttribute('r', '15');
  });
});
