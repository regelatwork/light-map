import React from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const MapLayer: React.FC = () => {
  const { config, isConnected } = useSystemState();

  if (!isConnected || !config.current_map_path || !config.map_width || !config.map_height) {
    return null;
  }

  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const mapUrl = `${host}/map/svg?map=${encodeURIComponent(config.current_map_path)}`;

  return (
    <image
      key={config.current_map_path}
      href={mapUrl}
      x={0}
      y={0}
      width={config.map_width}
      height={config.map_height}
      style={{ pointerEvents: 'none' }}
    />
  );
};
