import { render, screen, fireEvent } from '@testing-library/react';
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
    // Mock system state with a specific grid origin and NO rotation
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

    const { container, rerender } = render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );

    let svg = container.querySelector('svg');
    // For grid origin (250, 350) and a 1000x750 viewBox:
    // viewBox.x = 250 - 500 = -250
    // viewBox.y = 350 - 375 = -25
    expect(svg).toHaveAttribute('viewBox', '-250 -25 1000 750');

    // Test with ROTATION
    mockSystemState = {
      ...mockSystemState,
      world: {
        ...mockSystemState.world,
        viewport: { rotation: 90, x: 0, y: 0, zoom: 1 },
      },
    };

    rerender(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );

    // Initial centered ref is still true, so we need to click "Reset View" or use a new render
    const resetButton = screen.getByText(/Reset View/i);
    fireEvent.click(resetButton);

    svg = container.querySelector('svg');
    // Rotate (250, 350) 90 deg around (500, 375)
    // dx = 250 - 500 = -250
    // dy = 350 - 375 = -25
    // x' = -250 * cos(90) - (-25) * sin(90) + 500 = 0 - (-25) + 500 = 525
    // y' = -250 * sin(90) + (-25) * cos(90) + 375 = -250 + 0 + 375 = 125
    // viewBox.x = 525 - 500 = 25
    // viewBox.y = 125 - 375 = -250
    expect(svg).toHaveAttribute('viewBox', '25 -250 1000 750');
  });

  it('centers on 0,0 if grid origin is 0,0 and no rotation', () => {
    mockSystemState = {
      ...INITIAL_STATE,
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [],
      config: {
        ...INITIAL_STATE.config,
        proj_res: [1000, 750],
      },
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

    const svg = container.querySelector('svg');
    // viewBox.x = 0 - 500 = -500
    // viewBox.y = 0 - 375 = -375
    expect(svg).toHaveAttribute('viewBox', '-500 -375 1000 750');
  });
});
