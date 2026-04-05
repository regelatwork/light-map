import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SchematicCanvas } from './SchematicCanvas';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';
import { GridEditProvider } from './GridEditContext';
import { type SystemState, INITIAL_STATE } from '../types/system';

let mockSystemState: SystemState = {
  ...INITIAL_STATE,
  isConnected: true,
  world: { scene: 'MAP', fps: 60, blockers: [] },
  tokens: [
    { id: 1, world_x: 100, world_y: 100 },
    { id: 2, world_x: 200, world_y: 200 },
  ],
  config: {
    ...INITIAL_STATE.config,
    current_map_path: 'test.svg',
    map_width: 1000,
    map_height: 750,
  },
  grid_spacing_svg: 50,
  grid_origin_svg_x: 0,
  grid_origin_svg_y: 0,
};

// Mock the WebSocket
vi.mock('../hooks/useSystemState', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useSystemState: () => mockSystemState,
  };
});

describe('SchematicCanvas', () => {
  it('renders the background rect', () => {
    mockSystemState = {
      ...INITIAL_STATE,
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [
        { id: 1, world_x: 100, world_y: 100 },
        { id: 2, world_x: 200, world_y: 200 },
      ],
      config: {
        ...INITIAL_STATE.config,
        current_map_path: 'test.svg',
        map_width: 1000,
        map_height: 750,
      },
      grid_spacing_svg: 50,
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
    };
    const { container } = render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );
    const rect = container.querySelector('rect');
    expect(rect).toBeInTheDocument();
  });

  it('renders tokens', () => {
    render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );
    expect(screen.getByText(/#1/)).toBeInTheDocument();
    expect(screen.getByText(/#2/)).toBeInTheDocument();
  });

  it('renders reset button', () => {
    render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );
    expect(screen.getByText(/Reset View/i)).toBeInTheDocument();
  });

  it('centers on the grid origin if available', () => {
    // Mock system state with a specific grid origin
    mockSystemState = {
      ...INITIAL_STATE,
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [],
      config: {
        ...INITIAL_STATE.config,
        current_map_path: 'test.svg',
        map_width: 1000,
        map_height: 750,
        proj_res: [1000, 750],
      },
      grid_spacing_svg: 50,
      grid_origin_svg_x: 250,
      grid_origin_svg_y: 350,
    };

    const { container } = render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );

    const svg = container.querySelector('svg');
    // For grid origin (250, 350) and a 1000x750 viewBox:
    // viewBox.x = 250 - 500 = -250
    // viewBox.y = 350 - 375 = -25
    expect(svg).toHaveAttribute('viewBox', '-250 -25 1000 750');
  });
});
