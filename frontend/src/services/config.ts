/**
 * Configuration for API and WebSocket endpoints.
 * In development, defaults to localhost:8000.
 * In production, uses the current window location.
 * Can be overridden by the VITE_API_HOST environment variable.
 */

declare global {
  interface Window {
    VITE_API_HOST?: string;
  }
}

const getApiHost = () => {
  // Allow E2E tests to inject the host via window
  if (window.VITE_API_HOST) {
    return window.VITE_API_HOST;
  }

  // If VITE_API_HOST is provided via env, use it
  if (import.meta.env.VITE_API_HOST) {
    return import.meta.env.VITE_API_HOST;
  }
  
  // Default for development
  if (import.meta.env.DEV) {
    return 'localhost:8000';
  }

  // Use current window location for production
  return window.location.host;
};

export const API_HOST = getApiHost();
export const API_BASE_URL = `${window.location.protocol}//${API_HOST}`;
export const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
export const WS_URL = `${WS_PROTOCOL}//${API_HOST}/ws/state`;
