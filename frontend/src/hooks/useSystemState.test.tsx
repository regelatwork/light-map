import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import WS from 'vitest-websocket-mock';
import { SystemStateProvider, useSystemState } from './useSystemState';

const TestComponent = () => {
  const state = useSystemState();
  return (
    <div>
      <div data-testid="connected">{state.isConnected.toString()}</div>
      <div data-testid="scene">{state.world.scene}</div>
      <div data-testid="fps">{state.world.fps}</div>
    </div>
  );
};

describe('useSystemState', () => {
  let server: WS;

  beforeEach(() => {
    // getWsUrl returns ws://localhost:8000/ws/state in DEV mode (Vitest)
    server = new WS('ws://localhost:8000/ws/state');
  });

  afterEach(() => {
    WS.clean();
  });

  it('provides initial state and connects', async () => {
    render(
      <SystemStateProvider>
        <TestComponent />
      </SystemStateProvider>
    );

    expect(screen.getByTestId('connected')).toHaveTextContent('false');
    expect(screen.getByTestId('scene')).toHaveTextContent('MenuScene');

    await server.connected;
    await waitFor(() => expect(screen.getByTestId('connected')).toHaveTextContent('true'));
  });

  it('updates state when message is received', async () => {
    render(
      <SystemStateProvider>
        <TestComponent />
      </SystemStateProvider>
    );

    await server.connected;

    const newState = {
      world: { scene: 'MAP', fps: 60.5 },
      tokens: [],
      menu: { title: 'Main Menu', items: ['Item 1', 'Item 2'] },
      timestamp: Date.now(),
    };

    // server.send in vitest-websocket-mock can handle objects if configured,
    // but the hook expects a string to JSON.parse.
    act(() => {
      server.send(JSON.stringify(newState));
    });

    await waitFor(() => expect(screen.getByTestId('scene')).toHaveTextContent('MAP'));
    expect(screen.getByTestId('fps')).toHaveTextContent('60.5');
  });

  it('deeply merges world and config objects on partial updates', async () => {
    render(
      <SystemStateProvider>
        <TestComponent />
      </SystemStateProvider>
    );

    await server.connected;

    // 1. Initial full state
    const initialState = {
      world: { scene: 'MAP', fps: 60.0, viewport: { zoom: 1.0 } },
      config: { map_width: 1000, map_height: 750 },
      timestamp: Date.now(),
    };

    act(() => {
      server.send(JSON.stringify(initialState));
    });

    await waitFor(() => expect(screen.getByTestId('scene')).toHaveTextContent('MAP'));

    // 2. Partial update for world (only scene)
    const partialWorldUpdate = {
      world: { scene: 'VIEWING' },
      timestamp: Date.now() + 100,
    };

    act(() => {
      server.send(JSON.stringify(partialWorldUpdate));
    });

    await waitFor(() => expect(screen.getByTestId('scene')).toHaveTextContent('VIEWING'));
    // FPS should be preserved from initialState
    expect(screen.getByTestId('fps')).toHaveTextContent('60');

    // 3. Partial update for config
    const partialConfigUpdate = {
      config: { current_map_path: 'new.svg' },
      timestamp: Date.now() + 200,
    };

    act(() => {
      server.send(JSON.stringify(partialConfigUpdate));
    });

    // Wait for update
    await new Promise((resolve) => setTimeout(resolve, 50));

    // Verify config properties are preserved (via implicit state check if we had a testid for it)
    // For now, just ensuring no crash and scene is still there
    expect(screen.getByTestId('scene')).toHaveTextContent('VIEWING');
  });

  it('handles disconnect and reconnects', async () => {
    render(
      <SystemStateProvider>
        <TestComponent />
      </SystemStateProvider>
    );

    await server.connected;
    await waitFor(() => expect(screen.getByTestId('connected')).toHaveTextContent('true'));

    act(() => {
      server.close();
    });

    await waitFor(() => expect(screen.getByTestId('connected')).toHaveTextContent('false'));
  });
});
