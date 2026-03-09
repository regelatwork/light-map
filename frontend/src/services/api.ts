export const saveGridConfig = async (offset_x: number, offset_y: number) => {
  const host = import.meta.env.DEV ? 'http://localhost:8000' : '';
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
