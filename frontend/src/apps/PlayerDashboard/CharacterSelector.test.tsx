import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { CharacterSelector } from './CharacterSelector';

describe('CharacterSelector', () => {
  const mockOnSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Stub global fetch
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders loading state initially', async () => {
    // Return a promise that does not resolve immediately to keep loading = true
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}));

    render(<CharacterSelector onSelect={mockOnSelect} />);

    // Circular loading spinner is animated in the loading state
    expect(screen.queryByText('Claim Your Hero')).toBeInTheDocument();
    expect(screen.queryByText('No PC tokens found in configuration.')).not.toBeInTheDocument();
  });

  it('fetches config, filters PC players, and renders buttons', async () => {
    const mockConfig = {
      token_profiles: {},
      aruco_defaults: {
        '1': { name: 'Fighter', type: 'PC', color: '#ff0000' },
        '2': { name: 'Goblin', type: 'NPC', color: '#00ff00' },
        '3': { name: 'Wizard', type: 'PC', color: '#0000ff' },
      },
    };

    vi.mocked(fetch).mockResolvedValue({
      json: async () => mockConfig,
    } as Response);

    render(<CharacterSelector onSelect={mockOnSelect} />);

    // Wait for the loading state to resolve
    await waitFor(() => {
      expect(screen.getByText('Fighter')).toBeInTheDocument();
      expect(screen.getByText('Wizard')).toBeInTheDocument();
    });

    // Make sure NPC (Goblin) is not rendered
    expect(screen.queryByText('Goblin')).not.toBeInTheDocument();

    // Verify click handler triggers callback
    const fighterButton = screen.getByText('Fighter').closest('button');
    expect(fighterButton).toBeTruthy();
    fireEvent.click(fighterButton!);

    expect(mockOnSelect).toHaveBeenCalledWith('1');
  });

  it('renders fallback manual input when no PC characters are found', async () => {
    const mockConfig = {
      token_profiles: {},
      aruco_defaults: {
        '1': { name: 'Goblin', type: 'NPC' },
      },
    };

    vi.mocked(fetch).mockResolvedValue({
      json: async () => mockConfig,
    } as Response);

    render(<CharacterSelector onSelect={mockOnSelect} />);

    await waitFor(() => {
      expect(screen.getByText('No PC tokens found in configuration.')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Enter Token ID (e.g. 42)');
    const joinButton = screen.getByRole('button', { name: /join/i });

    expect(input).toBeInTheDocument();
    expect(joinButton).toBeInTheDocument();

    // Simulate entering an ID and joining
    fireEvent.change(input, { target: { value: '42' } });
    fireEvent.click(joinButton);

    expect(mockOnSelect).toHaveBeenCalledWith('42');
  });

  it('renders fallback manual input when fetch fails', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network error'));

    render(<CharacterSelector onSelect={mockOnSelect} />);

    await waitFor(() => {
      expect(screen.getByText('No PC tokens found in configuration.')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Enter Token ID (e.g. 42)');
    expect(input).toBeInTheDocument();
  });
});
