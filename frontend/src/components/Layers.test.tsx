import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MapLayer } from './MapLayer';
import { DoorLayer } from './DoorLayer';
import { FowLayer } from './FowLayer';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';
import { VisibilityType } from '../types/system';

// Mock the hook
vi.mock('../hooks/useSystemState', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useSystemState: () => ({
      isConnected: true,
      config: {
        current_map_path: 'test.svg',
        map_width: 1000,
        map_height: 750,
        fow_disabled: false,
      },
      world: {
        blockers: [
          {
            id: '1',
            type: VisibilityType.DOOR,
            is_open: false,
            points: [
              [10, 10],
              [20, 20],
            ],
          },
        ],
      },
      grid_spacing_svg: 50,
    }),
  };
});

describe('Layers', () => {
  it('renders MapLayer as an image', () => {
    const { container } = render(
      <SystemStateProvider>
        <SelectionProvider>
          <svg>
            <MapLayer />
          </svg>
        </SelectionProvider>
      </SystemStateProvider>
    );
    const img = container.querySelector('image');
    expect(img).toBeInTheDocument();
    expect(img?.getAttribute('href')).toContain('map/svg');
  });

  it('renders DoorLayer with polyline for closed door', () => {
    const { container } = render(
      <SystemStateProvider>
        <SelectionProvider>
          <svg>
            <DoorLayer />
          </svg>
        </SelectionProvider>
      </SystemStateProvider>
    );
    const polyline = container.querySelector('polyline');
    expect(polyline).toBeInTheDocument();
  });

  it('renders FowLayer as an image with filter', () => {
    const { container } = render(
      <SystemStateProvider>
        <SelectionProvider>
          <svg>
            <FowLayer />
          </svg>
        </SelectionProvider>
      </SystemStateProvider>
    );
    const img = container.querySelector('image');
    expect(img).toBeInTheDocument();
    expect(img?.getAttribute('href')).toContain('map/fow');
    expect(img?.getAttribute('filter')).toBe('url(#fow-invert-alpha)');
  });
});
