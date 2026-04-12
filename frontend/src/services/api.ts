import type { GlobalConfig } from '../types/schema.generated';

export const injectAction = async (action: string, payload?: string) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const url = new URL(`${host}/input/action`);
  url.searchParams.append('action', action);
  if (payload) {
    url.searchParams.append('payload', payload);
  }

  const response = await fetch(url.toString(), {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to inject action: ${action}`);
  }

  return response.json();
};

export const getMaps = async () => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/maps`);

  if (!response.ok) {
    throw new Error('Failed to fetch maps');
  }

  return response.json();
};

export const loadMap = async (path: string, loadSession: boolean = true) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const url = new URL(`${host}/map/load`);
  url.searchParams.append('path', path);
  url.searchParams.append('load_session', loadSession.toString());

  const response = await fetch(url.toString(), {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to load map: ${path}`);
  }

  return response.json();
};

export const saveGridConfig = async (offset_x: number, offset_y: number, spacing?: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/config/grid`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ offset_x, offset_y, spacing }),
  });

  if (!response.ok) {
    throw new Error('Failed to save grid configuration');
  }

  return response.json();
};

export const setViewportConfig = async (
  x: number,
  y: number,
  zoom: number,
  rotation: number
) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/config/viewport`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ x, y, zoom, rotation }),
  });

  if (!response.ok) {
    throw new Error('Failed to save viewport configuration');
  }

  return response.json();
};

export const interactMenu = async (index: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const url = new URL(`${host}/menu/interact`);
  url.searchParams.append('index', index.toString());

  const response = await fetch(url.toString(), {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to interact with menu at index: ${index}`);
  }

  return response.json();
};

export const updateToken = async (
  tokenId: number,
  update: {
    name?: string;
    color?: string;
    type?: string;
    profile?: string;
    size?: number;
    height_mm?: number;
    is_map_override?: boolean;
  },
) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/state/tokens/${tokenId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(update),
  });

  if (!response.ok) {
    throw new Error(`Failed to update token: ${tokenId}`);
  }

  return response.json();
};

export const deleteToken = async (tokenId: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/state/tokens/${tokenId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete token: ${tokenId}`);
  }

  return response.json();
};

export const deleteTokenOverride = async (tokenId: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/state/tokens/${tokenId}/override`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete token override: ${tokenId}`);
  }

  return response.json();
};

export const updateProfile = async (name: string, size: number, height_mm: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/state/profiles`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, size, height_mm }),
  });

  if (!response.ok) {
    throw new Error(`Failed to update profile: ${name}`);
  }

  return response.json();
};

export const deleteProfile = async (name: string) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/state/profiles/${name}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete profile: ${name}`);
  }

  return response.json();
};

export const updateSystemConfig = async (update: Partial<GlobalConfig>) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/config/system`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(update),
  });

  if (!response.ok) {
    throw new Error('Failed to update system configuration');
  }

  return response.json();
};
