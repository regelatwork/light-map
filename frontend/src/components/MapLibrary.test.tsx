import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MapLibrary } from './MapLibrary';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getMaps: vi.fn(),
  loadMap: vi.fn(),
}));

describe('MapLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly and is expanded by default', async () => {
    const mockMaps = [
      { path: 'map1.svg', name: 'Map 1' },
      { path: 'map2.svg', name: 'Map 2' },
    ];
    vi.mocked(api.getMaps).mockResolvedValue(mockMaps);

    render(<MapLibrary />);

    expect(screen.getByText('Map Library')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Map 1')).toBeInTheDocument();
      expect(screen.getByText('Map 2')).toBeInTheDocument();
    });
  });

  it('can be collapsed and expanded', async () => {
    const mockMaps = [{ path: 'map1.svg', name: 'Map 1' }];
    vi.mocked(api.getMaps).mockResolvedValue(mockMaps);

    render(<MapLibrary />);

    await waitFor(() => {
      expect(screen.getByText('Map 1')).toBeInTheDocument();
    });

    // Collapse
    const toggleButton = screen.getByRole('button', { name: /map library/i });
    fireEvent.click(toggleButton);

    expect(screen.queryByText('Map 1')).not.toBeInTheDocument();
    expect(screen.queryByText('Refresh')).not.toBeInTheDocument();

    // Expand
    fireEvent.click(toggleButton);
    expect(screen.getByText('Map 1')).toBeInTheDocument();
    expect(screen.getByText('Refresh')).toBeInTheDocument();
  });

  it('can refresh maps', async () => {
    vi.mocked(api.getMaps).mockResolvedValue([]);
    render(<MapLibrary />);

    await waitFor(() => {
      expect(api.getMaps).toHaveBeenCalledTimes(1);
    });

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(api.getMaps).toHaveBeenCalledTimes(2);
  });
});
