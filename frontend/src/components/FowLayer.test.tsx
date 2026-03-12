import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FowLayer } from './FowLayer';

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
        fow_disabled: false,
      },
      visibility_timestamp: 12345,
    })),
  };
});

import { useSystemState } from '../hooks/useSystemState';
import { type SystemState } from '../types/system';

describe('FowLayer', () => {
  it('renders the fow image when loading is successful', () => {
    render(
      <svg>
        <FowLayer />
      </svg>
    );

    const image = screen.getByTestId('fow-image');
    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute('href', expect.stringContaining('map=test-map.svg'));
    expect(image).toHaveAttribute('href', expect.stringContaining('v=12345'));
  });

  it('renders error message when image fails to load', () => {
    render(
      <svg>
        <FowLayer />
      </svg>
    );

    const image = screen.getByTestId('fow-image');
    fireEvent.error(image);

    expect(screen.queryByTestId('fow-image')).not.toBeInTheDocument();
    expect(screen.getByText(/Fog-of-war mask failed to load/i)).toBeInTheDocument();
  });

  it('resets error state when timestamp changes', () => {
    const { rerender } = render(
      <svg>
        <FowLayer />
      </svg>
    );

    const image = screen.getByTestId('fow-image');
    fireEvent.error(image);
    expect(screen.getByText(/Fog-of-war mask failed to load/i)).toBeInTheDocument();

    // Update mock to return a new timestamp
    vi.mocked(useSystemState).mockReturnValue({
      isConnected: true,
      config: {
        current_map_path: 'test-map.svg',
        map_width: 1000,
        map_height: 750,
        fow_disabled: false,
      },
      visibility_timestamp: 67890,
    } as unknown as SystemState);

    rerender(
      <svg>
        <FowLayer />
      </svg>
    );

    expect(screen.getByTestId('fow-image')).toBeInTheDocument();
    expect(screen.queryByText(/Fog-of-war mask failed to load/i)).not.toBeInTheDocument();
  });
});
