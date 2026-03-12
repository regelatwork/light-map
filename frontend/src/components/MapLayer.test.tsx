import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MapLayer } from './MapLayer';

// Mock useSystemState
vi.mock('../hooks/useSystemState', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useSystemState: vi.fn(() => ({
      isConnected: true,
      config: {
        current_map_path: 'test-map.svg',
        map_width: 1000,
        map_height: 750,
      },
    })),
  };
});

import { useSystemState } from '../hooks/useSystemState';
import { type SystemState } from '../types/system';

describe('MapLayer', () => {
  it('renders the map image when loading is successful', () => {
    render(
      <svg>
        <MapLayer />
      </svg>
    );

    const image = screen.getByTestId('map-image');
    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute('href', expect.stringContaining('test-map.svg'));
  });

  it('renders error placeholder when image fails to load', () => {
    render(
      <svg>
        <MapLayer />
      </svg>
    );

    const image = screen.getByTestId('map-image');
    fireEvent.error(image);

    expect(screen.queryByTestId('map-image')).not.toBeInTheDocument();
    expect(screen.getByText(/Failed to load map asset: test-map.svg/i)).toBeInTheDocument();
  });

  it('resets error state when map path changes', () => {
    const { rerender } = render(
      <svg>
        <MapLayer />
      </svg>
    );

    const image = screen.getByTestId('map-image');
    fireEvent.error(image);
    expect(screen.getByText(/Failed to load map asset/i)).toBeInTheDocument();

    // Update mock to return a new map path
    vi.mocked(useSystemState).mockReturnValue({
      isConnected: true,
      config: {
        current_map_path: 'new-map.svg',
        map_width: 1000,
        map_height: 750,
      },
    } as unknown as SystemState);

    rerender(
      <svg>
        <MapLayer />
      </svg>
    );

    expect(screen.getByTestId('map-image')).toBeInTheDocument();
    expect(screen.queryByText(/Failed to load map asset/i)).not.toBeInTheDocument();
  });
});
