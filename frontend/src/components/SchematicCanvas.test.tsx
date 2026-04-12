import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SchematicCanvas } from './SchematicCanvas';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';
import { CalibrationProvider } from './CalibrationContext';
import { type SystemState, INITIAL_STATE } from '../types/system';

let mockSystemState: SystemState = {
  ...INITIAL_STATE,
  isConnected: true,
  world: { scene: 'MAP', fps: 60, blockers: [] },
  tokens: [
    { id: 1, world_x: 100, world_y: 100 } as any,
    { id: 2, world_x: 200, world_y: 200 } as any,
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
        { id: 1, world_x: 100, world_y: 100 } as any,
        { id: 2, world_x: 200, world_y: 200 } as any,
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
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );
    const rect = container.querySelector('rect');
    expect(rect).toBeInTheDocument();
  });

  it('renders tokens', () => {
    render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );
    expect(screen.getByText(/#1/)).toBeInTheDocument();
    expect(screen.getByText(/#2/)).toBeInTheDocument();
  });

  it('renders reset button', () => {
    render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
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
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
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
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
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

  it('centers on map center if grid origin is 0,0 and map dimensions available', () => {
    mockSystemState = {
      ...INITIAL_STATE,
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [],
      config: {
        ...INITIAL_STATE.config,
        current_map_path: 'test.svg',
        map_width: 800,
        map_height: 600,
        proj_res: [1000, 750],
      },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
    };

    const { container } = render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );

    const svg = container.querySelector('svg');
    // Target is map center: (400, 300)
    // viewBox.x = 400 - 500 = -100
    // viewBox.y = 300 - 375 = -75
    expect(svg).toHaveAttribute('viewBox', '-100 -75 1000 750');
  });

  it('centers on projection center if grid origin is 0,0 and no map dimensions', () => {
    mockSystemState = {
      ...INITIAL_STATE,
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [],
      config: {
        ...INITIAL_STATE.config,
        current_map_path: 'test.svg',
        proj_res: [1000, 750],
      },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
    };

    const { container } = render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );

    const svg = container.querySelector('svg');
    // Target is projection center: (500, 375)
    // viewBox.x = 500 - 500 = 0
    // viewBox.y = 375 - 375 = 0
    expect(svg).toHaveAttribute('viewBox', '0 0 1000 750');
  });

  it('does not center if current_map_path is missing', () => {
    mockSystemState = {
      ...INITIAL_STATE,
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [],
      config: {
        ...INITIAL_STATE.config,
        current_map_path: '', // Missing map path
        proj_res: [1000, 750],
      },
      grid_origin_svg_x: 100,
      grid_origin_svg_y: 100,
    };

    const { container } = render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <SchematicCanvas />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );

    const svg = container.querySelector('svg');
    // Should stay at initial state: -500 -375 1000 750
    expect(svg).toHaveAttribute('viewBox', '-500 -375 1000 750');
  });
});
