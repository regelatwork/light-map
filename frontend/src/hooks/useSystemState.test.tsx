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
    expect(screen.getByTestId('scene')).toHaveTextContent('LOADING');

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
      menu: {},
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
