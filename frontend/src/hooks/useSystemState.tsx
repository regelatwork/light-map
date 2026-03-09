import React, {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
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
      return { ...state, ...action.payload, isConnected: true, error: null };
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
  // Use a relative path in production, and point to 8000 in dev if not served by FastAPI
  const host = import.meta.env.DEV ? 'localhost:8000' : window.location.host;
  return `${protocol}//${host}/ws/state`;
};

export const SystemStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(systemReducer, INITIAL_STATE);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = () => {
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
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      dispatch({ type: 'SET_ERROR', payload: 'Connection error' });
      socket.close();
    };

    socketRef.current = socket;
  };

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
  }, []);

  return <SystemStateContext.Provider value={state}>{children}</SystemStateContext.Provider>;
};

export const useSystemState = () => useContext(SystemStateContext);
