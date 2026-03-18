/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
  useCallback,
  type ReactNode,
} from 'react';
import { type SystemState, INITIAL_STATE } from '../types/system';

type Action =
  | { type: 'UPDATE_STATE'; payload: Partial<SystemState> }
  | { type: 'SET_CONNECTED'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

function systemReducer(state: SystemState, action: Action): SystemState {
  switch (action.type) {
    case 'UPDATE_STATE':
      if (import.meta.env.DEV) {
        console.debug('State Update:', action.payload);
      }
      return {
        ...state,
        ...action.payload,
        // Deeply merge world and config if they exist in the payload
        world: action.payload.world ? { ...state.world, ...action.payload.world } : state.world,
        config: action.payload.config ? { ...state.config, ...action.payload.config } : state.config,
        isConnected: true,
        error: null,
      };
    case 'SET_CONNECTED':
      return { ...state, isConnected: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isConnected: false };
    default:
      return state;
  }
}

const SystemStateContext = createContext<SystemState>(INITIAL_STATE);

const getWsUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.DEV ? 'localhost:8000' : window.location.host;
  return `${protocol}//${host}/ws/state`;
};

export const SystemStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(systemReducer, INITIAL_STATE);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const url = getWsUrl();
    const socket = new WebSocket(url);

    socket.onopen = () => {
      console.log('WebSocket connected to', url);
      dispatch({ type: 'SET_CONNECTED', payload: true });
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        dispatch({ type: 'UPDATE_STATE', payload: data });
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected. Reconnecting in 3s...');
      dispatch({ type: 'SET_CONNECTED', payload: false });
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectRef.current();
      }, 3000);
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      dispatch({ type: 'SET_ERROR', payload: 'Connection error' });
      socket.close();
    };

    socketRef.current = socket;
  }, []);

  // Update the ref so it always points to the stable connect function
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return <SystemStateContext.Provider value={state}>{children}</SystemStateContext.Provider>;
};

export const useSystemState = () => useContext(SystemStateContext);
