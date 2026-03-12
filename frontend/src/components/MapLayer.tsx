import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const MapLayer: React.FC = () => {
  const { config, isConnected } = useSystemState();
  const [errorPath, setErrorPath] = useState<string | null>(null);

  const hasError = errorPath === config.current_map_path;

  if (!isConnected || !config.current_map_path || !config.map_width || !config.map_height) {
    return null;
  }

  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const mapUrl = `${host}/map/svg?map=${encodeURIComponent(config.current_map_path)}`;

  if (hasError) {
    return (
      <g id="map-error-placeholder">
        <rect
          x={0}
          y={0}
          width={config.map_width}
          height={config.map_height}
          fill="#fee2e2"
          stroke="#ef4444"
          strokeWidth={4}
          strokeDasharray="10,10"
        />
        <text
          x={config.map_width / 2}
          y={config.map_height / 2}
          textAnchor="middle"
          fill="#b91c1c"
          className="text-lg font-bold select-none"
          style={{ pointerEvents: 'none' }}
        >
          Failed to load map asset: {config.current_map_path}
        </text>
      </g>
    );
  }

  return (
    <image
      key={config.current_map_path}
      href={mapUrl}
      x={0}
      y={0}
      width={config.map_width}
      height={config.map_height}
      style={{ pointerEvents: 'none' }}
      onError={() => setErrorPath(config.current_map_path)}
      data-testid="map-image"
    />
  );
};
