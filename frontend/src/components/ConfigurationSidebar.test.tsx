import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConfigurationSidebar } from './ConfigurationSidebar';
import * as useSystemStateHook from '../hooks/useSystemState';
import * as useSelectionHook from './SelectionContext';
import * as useGridEditHook from './GridEditContext';
import { SelectionType, GmPosition } from '../types/system';
import { updateToken } from '../services/api';

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

vi.mock('./GridEditContext', () => ({
  useGridEdit: vi.fn(),
}));

describe('ConfigurationSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useGridEditHook.useGridEdit).mockReturnValue({
      isGridEditMode: false,
      setIsGridEditMode: vi.fn(),
    });
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
        gm_position: GmPosition.NONE,
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

  it('allows updating token type and name', () => {
    const mockToken = {
      id: 1,
      name: 'Test Token',
      world_x: 10.5,
      world_y: 20.7,
      color: '#ff0000',
      type: 'NPC',
    };

    vi.mocked(useSystemStateHook.useSystemState).mockReturnValue({
      tokens: [mockToken],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: GmPosition.NONE,
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

    // Check Type buttons
    const npcButton = screen.getByText('NPC');
    const pcButton = screen.getByText('PC');

    expect(npcButton).toHaveClass('bg-blue-600'); // Selected by default
    expect(pcButton).toHaveClass('bg-white');

    // Toggle to PC
    fireEvent.click(pcButton);
    expect(updateToken).toHaveBeenCalledWith(1, { type: 'PC' });

    // Update Name
    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'New Hero' } });
    fireEvent.blur(nameInput);
    expect(updateToken).toHaveBeenCalledWith(1, { name: 'New Hero' });
  });

  it('allows updating advanced token properties', () => {
    const mockToken = {
      id: 1,
      name: 'Test Token',
      world_x: 10.5,
      world_y: 20.7,
      color: '#ff0000',
      type: 'NPC',
      profile: 'std',
      size: 1,
      height_mm: 10,
    };

    vi.mocked(useSystemStateHook.useSystemState).mockReturnValue({
      tokens: [mockToken],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: GmPosition.NONE,
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

    // Show Advanced
    fireEvent.click(screen.getByText(/Show Advanced Properties/i));

    // Update Profile
    const profileInput = screen.getByLabelText('Token Profile');
    fireEvent.change(profileInput, { target: { value: 'large_token' } });
    fireEvent.blur(profileInput);
    expect(updateToken).toHaveBeenCalledWith(1, { profile: 'large_token' });

    // Update Size
    const sizeInput = screen.getByLabelText('Size (Grid)');
    fireEvent.change(sizeInput, { target: { value: '2' } });
    fireEvent.blur(sizeInput);
    expect(updateToken).toHaveBeenCalledWith(1, { size: 2 });

    // Update Height
    const heightInput = screen.getByLabelText('Height (mm)');
    fireEvent.change(heightInput, { target: { value: '25' } });
    fireEvent.blur(heightInput);
    expect(updateToken).toHaveBeenCalledWith(1, { height_mm: 25 });
  });
});
