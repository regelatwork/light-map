import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConfigurationSidebar } from './ConfigurationSidebar';
import * as useSystemStateHook from '../hooks/useSystemState';
import * as useSelectionHook from './SelectionContext';
import { SelectionType } from '../types/system';

// Mock the services/api to avoid actual network requests
vi.mock('../services/api', () => ({
  saveGridConfig: vi.fn(),
  injectAction: vi.fn(),
  updateToken: vi.fn(),
}));

vi.mock('../hooks/useSystemState', () => ({
  useSystemState: vi.fn(),
}));

vi.mock('./SelectionContext', () => ({
  useSelection: vi.fn(),
}));

describe('ConfigurationSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hides World X/Y by default and shows them when Advanced is toggled', () => {
    const mockToken = {
      id: 1,
      name: 'Test Token',
      world_x: 10.5,
      world_y: 20.7,
      color: '#ff0000',
    };

    vi.mocked(useSystemStateHook.useSystemState).mockReturnValue({
      tokens: [mockToken],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: 'None' as any,
        debug_mode: false,
        enable_hand_masking: false,
        fow_disabled: false,
      },
      timestamp: 0,
      isConnected: true,
      error: null,
      grid_spacing_svg: 50,
      visibility_timestamp: 0,
      menu: null,
    });

    vi.mocked(useSelectionHook.useSelection).mockReturnValue({
      selection: { type: SelectionType.TOKEN, id: 1 },
      setSelection: vi.fn(),
    });

    render(<ConfigurationSidebar />);

    // By default, World X/Y should not be visible (this test will FAIL until we implement it)
    expect(screen.queryByText('World X')).not.toBeInTheDocument();
    expect(screen.queryByText('World Y')).not.toBeInTheDocument();

    // Find the toggle button
    const toggleButton = screen.getByText(/Show Advanced Properties/i);
    expect(toggleButton).toBeInTheDocument();

    // Click the toggle
    fireEvent.click(toggleButton);

    // Now World X/Y should be visible
    expect(screen.getByText('World X')).toBeInTheDocument();
    expect(screen.getByText('World Y')).toBeInTheDocument();
    expect(screen.getByDisplayValue('10.50')).toBeInTheDocument();
    expect(screen.getByDisplayValue('20.70')).toBeInTheDocument();

    // Toggle back
    fireEvent.click(screen.getByText(/Hide Advanced Properties/i));
    expect(screen.queryByText('World X')).not.toBeInTheDocument();
  });
});
