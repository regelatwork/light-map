import type { GlobalConfig, CoverResult } from '../types/schema.generated';
import { GridType } from '../types/system';
import { API_BASE_URL } from './config';

export const injectAction = async (action: string, payload?: string) => {
  const url = new URL(`${API_BASE_URL}/input/action`);
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
  const response = await fetch(`${API_BASE_URL}/maps`);

  if (!response.ok) {
    throw new Error('Failed to fetch maps');
  }

  return response.json();
};

export const loadMap = async (path: string, loadSession: boolean = true) => {
  const url = new URL(`${API_BASE_URL}/map/load`);
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

export const saveGridConfig = async (
  offset_x: number,
  offset_y: number,
  spacing?: number,
  grid_type?: GridType,
  visible?: boolean,
  color?: string
) => {
  const response = await fetch(`${API_BASE_URL}/config/grid`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ offset_x, offset_y, spacing, grid_type, visible, color }),
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
  const response = await fetch(`${API_BASE_URL}/config/viewport`, {
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
  const url = new URL(`${API_BASE_URL}/menu/interact`);
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
  const response = await fetch(`${API_BASE_URL}/state/tokens/${tokenId}`, {
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
  const response = await fetch(`${API_BASE_URL}/state/tokens/${tokenId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete token: ${tokenId}`);
  }

  return response.json();
};

export const deleteTokenOverride = async (tokenId: number) => {
  const response = await fetch(`${API_BASE_URL}/state/tokens/${tokenId}/override`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete token override: ${tokenId}`);
  }

  return response.json();
};

export const updateProfile = async (name: string, size: number, height_mm: number) => {
  const response = await fetch(`${API_BASE_URL}/state/profiles`, {
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
  const response = await fetch(`${API_BASE_URL}/state/profiles/${name}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete profile: ${name}`);
  }

  return response.json();
};

export const updateSystemConfig = async (update: Partial<GlobalConfig>) => {
  const response = await fetch(`${API_BASE_URL}/config/system`, {
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

export const getTacticalCover = async (attackerId?: number): Promise<Record<number, CoverResult>> => {
  const url = new URL(`${API_BASE_URL}/tactical/cover`);
  if (attackerId !== undefined) {
    url.searchParams.append('attacker_id', attackerId.toString());
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error('Failed to fetch tactical cover data');
  }

  return response.json();
};
