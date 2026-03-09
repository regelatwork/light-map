import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SchematicCanvas } from './SchematicCanvas';
import { SystemStateProvider } from '../hooks/useSystemState';

// Mock the WebSocket
vi.mock('../hooks/useSystemState', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useSystemState: () => ({
      isConnected: true,
      world: { scene: 'MAP', fps: 60 },
      tokens: [
        { id: 1, world_x: 100, world_y: 100 },
        { id: 2, world_x: 200, world_y: 200 },
      ],
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
        <SchematicCanvas />
      </SystemStateProvider>
    );
    const rect = container.querySelector('rect');
    expect(rect).toBeInTheDocument();
  });

  it('renders tokens', () => {
    render(
      <SystemStateProvider>
        <SchematicCanvas />
      </SystemStateProvider>
    );
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('renders reset button', () => {
    render(
      <SystemStateProvider>
        <SchematicCanvas />
      </SystemStateProvider>
    );
    expect(screen.getByText(/Reset View/i)).toBeInTheDocument();
  });
});
