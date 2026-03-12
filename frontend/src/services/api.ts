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

export const saveGridConfig = async (offset_x: number, offset_y: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const response = await fetch(`${host}/config/grid`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ offset_x, offset_y }),
  });

  if (!response.ok) {
    throw new Error('Failed to save grid configuration');
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

export const updateToken = async (tokenId: number, update: { name?: string; color?: string }) => {
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
