import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SchematicCanvas } from './SchematicCanvas';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';

// Mock the WebSocket
vi.mock('../hooks/useSystemState', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useSystemState: () => ({
      isConnected: true,
      world: { scene: 'MAP', fps: 60, blockers: [] },
      tokens: [
        { id: 1, world_x: 100, world_y: 100 },
        { id: 2, world_x: 200, world_y: 200 },
      ],
      config: {
        fow_disabled: false,
        current_map_path: 'test.svg',
        map_width: 1000,
        map_height: 750,
      },
      grid_spacing_svg: 50,
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
    }),
  };
});

describe('SchematicCanvas', () => {
  it('renders the background rect', () => {
    const { container } = render(
      <SystemStateProvider>
        <SelectionProvider>
          <SchematicCanvas />
        </SelectionProvider>
      </SystemStateProvider>
    );
    const rect = container.querySelector('rect');
    expect(rect).toBeInTheDocument();
  });

  it('renders tokens', () => {
    render(
      <SystemStateProvider>
        <SelectionProvider>
          <SchematicCanvas />
        </SelectionProvider>
      </SystemStateProvider>
    );
    expect(screen.getByText(/#1/)).toBeInTheDocument();
    expect(screen.getByText(/#2/)).toBeInTheDocument();
  });

  it('renders reset button', () => {
    render(
      <SystemStateProvider>
        <SelectionProvider>
          <SchematicCanvas />
        </SelectionProvider>
      </SystemStateProvider>
    );
    expect(screen.getByText(/Reset View/i)).toBeInTheDocument();
  });
});
