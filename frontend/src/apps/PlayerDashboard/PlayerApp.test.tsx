import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import WS from 'vitest-websocket-mock';
import { PlayerApp } from './PlayerApp';

// We mock CharacterSelector to focus tests on PlayerApp core states
vi.mock('./CharacterSelector', () => ({
  CharacterSelector: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <div>
      <button onClick={() => onSelect('42')}>Mock Claim Hero 42</button>
    </div>
  ),
}));

describe('PlayerApp', () => {
  let wsServer: WS;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Setup websocket mock server
    wsServer = new WS('ws://localhost:8000/ws/state');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true } as Response));
  });

  afterEach(() => {
    WS.clean();
    vi.unstubAllGlobals();
  });

  it('renders CharacterSelector if no token is selected', async () => {
    render(<PlayerApp />);

    expect(screen.getByText('Mock Claim Hero 42')).toBeInTheDocument();
    expect(screen.queryByText('Tactical Dashboard')).not.toBeInTheDocument();
  });

  it('renders Tactical Dashboard once a character is selected', async () => {
    render(<PlayerApp />);

    // Click mock button to select a hero
    fireEvent.click(screen.getByText('Mock Claim Hero 42'));

    // Dashboard should now render
    expect(screen.getByText('Tactical Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Token ID: 42')).toBeInTheDocument();
  });

  it('updates dashboard targets upon receiving WebSocket state updates', async () => {
    // Set active selection in localStorage
    localStorage.setItem('player_selected_token_id', '42');

    render(<PlayerApp />);

    expect(screen.getByText('Tactical Dashboard')).toBeInTheDocument();
    expect(screen.getByText('No enemies currently in sight.')).toBeInTheDocument();

    await wsServer.connected;

    // Send mock world state broadcast via websocket
    const mockState = {
      world: {
        tactical: {
          attacker_id: '42',
          is_exclusive_active: false,
          targets: [
            { id: 99, name: 'Orc Warrior', ac_bonus: 2, reflex_bonus: 0, reason: 'Partial Cover' },
          ],
        },
      },
    };

    wsServer.send(JSON.stringify(mockState));

    // Dashboard should update to show target list
    await waitFor(() => {
      expect(screen.getByText('Orc Warrior')).toBeInTheDocument();
      expect(screen.queryByText('No enemies currently in sight.')).not.toBeInTheDocument();
    });
  });

  it('sends POST action to exclusive vision endpoint when toggled', async () => {
    localStorage.setItem('player_selected_token_id', '42');
    render(<PlayerApp />);

    await wsServer.connected;

    // Initially exclusive vision is disabled
    wsServer.send(
      JSON.stringify({
        world: {
          tactical: {
            attacker_id: '42',
            is_exclusive_active: false,
            targets: [],
          },
        },
      })
    );

    await waitFor(() => {
      expect(screen.getByText('ENABLE EXCLUSIVE VISION')).toBeInTheDocument();
    });

    const toggleButton = screen.getByText('ENABLE EXCLUSIVE VISION');
    fireEvent.click(toggleButton);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/actions/exclusive-vision'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ token_id: '42' }),
      })
    );
  });
});
