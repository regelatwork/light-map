import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConfigurationSidebar } from './ConfigurationSidebar';
import * as useSystemStateHook from '../hooks/useSystemState';
import * as useSelectionHook from './SelectionContext';
import * as useCalibrationHook from './CalibrationContext';
import { SelectionType, GmPosition, VisibilityType, type Token } from '../types/system';
import { updateToken } from '../services/api';

// Mock the services/api to avoid actual network requests
vi.mock('../services/api', () => ({
  saveGridConfig: vi.fn(),
  injectAction: vi.fn(),
  updateToken: vi.fn(),
  deleteTokenOverride: vi.fn(),
  deleteToken: vi.fn(),
}));

vi.mock('../hooks/useSystemState', () => ({
  useSystemState: vi.fn(),
  INITIAL_STATE: {
    world: { scene: 'MENU', fps: 0 },
    tokens: [],
    menu: null,
    config: {
      cam_res: [0, 0],
      proj_res: [0, 0],
      enable_hand_masking: false,
      enable_aruco_masking: true,
      gm_position: 'None',
      debug_mode: false,
      fow_disabled: false,
      use_projector_3d_model: true,
    },
    maps: {},
    timestamp: 0,
    isConnected: false,
    error: null,
    grid_spacing_svg: 0,
    grid_origin_svg_x: 0,
    grid_origin_svg_y: 0,
    map_timestamp: 0,
    menu_timestamp: 0,
    tokens_timestamp: 0,
    raw_aruco_timestamp: 0,
    hands_timestamp: 0,
    scene_timestamp: 0,
    notifications_timestamp: 0,
    viewport_timestamp: 0,
    visibility_timestamp: 0,
    fow_timestamp: 0,
  },
}));

vi.mock('./SelectionContext', () => ({
  useSelection: vi.fn(),
}));

vi.mock('./CalibrationContext', () => ({
  useCalibration: vi.fn(),
  CalibrationMode: {
    NONE: 'NONE',
    GRID: 'GRID',
    VIEWPORT: 'VIEWPORT',
  },
}));

interface CalibrationMock {
  activeMode: useCalibrationHook.CalibrationMode;
  setMode: (mode: useCalibrationHook.CalibrationMode) => void;
}

describe('ConfigurationSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useCalibrationHook.useCalibration).mockReturnValue({
      activeMode: useCalibrationHook.CalibrationMode.NONE,
      setMode: vi.fn(),
    } as CalibrationMock);
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
      ...useSystemStateHook.INITIAL_STATE,
      tokens: [mockToken as unknown as Token],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: GmPosition.NONE,
        debug_mode: false,
        enable_hand_masking: false,
        enable_aruco_masking: true,
        fow_disabled: false,
        use_projector_3d_model: true,
        token_profiles: {
          small: { size: 1, height_mm: 15 },
          large: { size: 2, height_mm: 40 },
        },
      },
      maps: {},
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

    // By default, World X/Y should not be visible
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
      ...useSystemStateHook.INITIAL_STATE,
      tokens: [mockToken as unknown as Token],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: GmPosition.NONE,
        debug_mode: false,
        enable_hand_masking: false,
        enable_aruco_masking: true,
        fow_disabled: false,
        use_projector_3d_model: true,
        token_profiles: {
          small: { size: 1, height_mm: 15 },
          large: { size: 2, height_mm: 40 },
        },
      },
      maps: {},
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
    expect(updateToken).toHaveBeenCalledWith(1, expect.objectContaining({ type: 'PC' }));

    // Update Name
    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'New Hero' } });
    fireEvent.blur(nameInput);
    expect(updateToken).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'New Hero' }));
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
      ...useSystemStateHook.INITIAL_STATE,
      tokens: [mockToken as unknown as Token],
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: GmPosition.NONE,
        debug_mode: false,
        enable_hand_masking: false,
        enable_aruco_masking: true,
        fow_disabled: false,
        use_projector_3d_model: true,
        token_profiles: {
          small: { size: 1, height_mm: 15 },
          large: { size: 2, height_mm: 40 },
        },
      },
      maps: {},
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
    const profileSelect = screen.getByLabelText('Token Profile');
    fireEvent.change(profileSelect, { target: { value: 'large' } });
    expect(updateToken).toHaveBeenCalledWith(1, expect.objectContaining({ profile: 'large' }));

    // Size and Height should now be disabled
    const sizeInput = screen.getByLabelText('Size (Grid)');
    const heightInput = screen.getByLabelText('Height (mm)');
    expect(sizeInput).toBeDisabled();
    expect(heightInput).toBeDisabled();

    // Toggle back to Custom
    fireEvent.change(profileSelect, { target: { value: '' } });
    expect(updateToken).toHaveBeenCalledWith(1, expect.objectContaining({ profile: undefined }));

    // Size and Height should now be enabled
    expect(sizeInput).not.toBeDisabled();
    expect(heightInput).not.toBeDisabled();

    // Update Size
    fireEvent.change(sizeInput, { target: { value: '2' } });
    fireEvent.blur(sizeInput);
    expect(updateToken).toHaveBeenCalledWith(1, expect.objectContaining({ size: 2 }));

    // Update Height
    fireEvent.change(heightInput, { target: { value: '25' } });
    fireEvent.blur(heightInput);
    expect(updateToken).toHaveBeenCalledWith(1, expect.objectContaining({ height_mm: 25 }));
  });

  it('allows editing an arbitrary ArUco ID via Quick-Edit', () => {
    vi.mocked(useSystemStateHook.useSystemState).mockReturnValue({
      ...useSystemStateHook.INITIAL_STATE,
      tokens: [], // No live tokens
      world: { scene: 'VIEWING', fps: 60, blockers: [] },
      grid_origin_svg_x: 0,
      grid_origin_svg_y: 0,
      config: {
        cam_res: [1280, 720],
        proj_res: [1920, 1080],
        gm_position: GmPosition.NONE,
        debug_mode: false,
        enable_hand_masking: false,
        enable_aruco_masking: true,
        fow_disabled: false,
        use_projector_3d_model: true,
        aruco_defaults: {
          42: { name: 'Deep Thought', type: 'NPC', color: '#0000ff' },
        },
      },
      maps: {},
      timestamp: 0,
      isConnected: true,
      error: null,
      grid_spacing_svg: 50,
      visibility_timestamp: 0,
      menu: null,
    });

    const setSelection = vi.fn();
    vi.mocked(useSelectionHook.useSelection).mockReturnValue({
      selection: { type: SelectionType.NONE, id: null },
      setSelection,
    });

    const { unmount } = render(<ConfigurationSidebar />);

    // Find the Quick-Edit input
    const quickEditInput = screen.getByPlaceholderText('ID (e.g. 12)');
    fireEvent.change(quickEditInput, { target: { value: '42' } });

    // Verify setSelection was called
    expect(setSelection).toHaveBeenCalledWith({ type: SelectionType.TOKEN, id: '42' });

    // Mock update to show the token is now "selected"
    vi.mocked(useSelectionHook.useSelection).mockReturnValue({
      selection: { type: SelectionType.TOKEN, id: 42 },
      setSelection,
    });
    
    unmount(); // Remove the old instance
    render(<ConfigurationSidebar />);

    // Verify properties from aruco_defaults are shown
    expect(screen.getByText('Deep Thought (#42)')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Deep Thought')).toBeInTheDocument();

    // Update name
    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'The Answer' } });
    fireEvent.blur(nameInput);
    expect(updateToken).toHaveBeenCalledWith(42, expect.objectContaining({ name: 'The Answer' }));
  });

  it('shows door properties even if a token was previously selected (regression test)', () => {
    const mockToken = { id: 1, name: 'Token 1', world_x: 0, world_y: 0 };
    const mockDoor = {
      id: 'door-1',
      type: VisibilityType.DOOR,
      is_open: false,
      points: [],
    };

    const systemState = {
      ...useSystemStateHook.INITIAL_STATE,
      tokens: [mockToken as unknown as Token],
      world: { scene: 'VIEWING', fps: 60, blockers: [mockDoor] },
      config: {
        ...useSystemStateHook.INITIAL_STATE.config,
        gm_position: GmPosition.NONE,
        use_projector_3d_model: true,
      },
    };

    vi.mocked(useSystemStateHook.useSystemState).mockReturnValue(systemState);

    const setSelection = vi.fn();

    // 1. Initial selection is TOKEN 1
    vi.mocked(useSelectionHook.useSelection).mockReturnValue({
      selection: { type: SelectionType.TOKEN, id: 1 },
      setSelection,
    });

    const { rerender } = render(<ConfigurationSidebar />);

    // Check that token properties are shown
    expect(screen.getByText('Token 1 (#1)')).toBeInTheDocument();

    // 2. Selection changes to DOOR
    vi.mocked(useSelectionHook.useSelection).mockReturnValue({
      selection: { type: SelectionType.DOOR, id: 'door-1' },
      setSelection,
    });

    rerender(<ConfigurationSidebar />);

    // Verify door properties are shown and token properties are gone
    expect(screen.getByText('Door Selected')).toBeInTheDocument();
    expect(screen.queryByText('Token 1 (#1)')).not.toBeInTheDocument();
  });

  it('allows toggling Visual Grid Editor and shows origin inputs when enabled', () => {
    const setMode = vi.fn();
    vi.mocked(useCalibrationHook.useCalibration).mockReturnValue({
      activeMode: useCalibrationHook.CalibrationMode.NONE,
      setMode,
    } as CalibrationMock);

    vi.mocked(useSystemStateHook.useSystemState).mockReturnValue({
      ...useSystemStateHook.INITIAL_STATE,
      grid_origin_svg_x: 100,
      grid_origin_svg_y: 200,
      isConnected: true,
      config: {
        ...useSystemStateHook.INITIAL_STATE.config,
        gm_position: GmPosition.NONE,
        use_projector_3d_model: true,
      },
    });

    vi.mocked(useSelectionHook.useSelection).mockReturnValue({
      selection: { type: SelectionType.NONE, id: null },
      setSelection: vi.fn(),
    });

    const { rerender } = render(<ConfigurationSidebar />);

    // Check for the toggle
    const toggleButton = screen.getByRole('button', { name: /Visual Grid Editor/i });
    expect(toggleButton).toBeInTheDocument();

    // Origin inputs should not be visible
    expect(screen.queryByLabelText(/Origin X/i)).not.toBeInTheDocument();

    // Click the toggle
    fireEvent.click(toggleButton);
    expect(setMode).toHaveBeenCalledWith(useCalibrationHook.CalibrationMode.GRID);

    // Now mock it as enabled
    vi.mocked(useCalibrationHook.useCalibration).mockReturnValue({
      activeMode: useCalibrationHook.CalibrationMode.GRID,
      setMode,
    } as CalibrationMock);

    rerender(<ConfigurationSidebar />);

    // Origin inputs should now be visible with correct values
    expect(screen.getByLabelText(/Origin X/i)).toHaveValue(100);
    expect(screen.getByLabelText(/Origin Y/i)).toHaveValue(200);
  });
});
