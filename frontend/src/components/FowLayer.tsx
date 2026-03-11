import React from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const FowLayer: React.FC = () => {
  const { config, isConnected, visibility_timestamp } = useSystemState();

  if (
    !isConnected ||
    !config.current_map_path ||
    !config.map_width ||
    !config.map_height ||
    config.fow_disabled
  ) {
    return null;
  }

  const host = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin;
  const fowUrl = `${host}/map/fow?map=${encodeURIComponent(config.current_map_path)}&v=${visibility_timestamp}`;

  return (
    <g id="fow-layer">
      <defs>
        <filter id="fow-invert-alpha">
          {/* 
            Inverts grayscale to alpha: 
            White (255) -> Alpha 0 (Revealed)
            Black (0) -> Alpha 1 (Opaque Fog)
          */}
          <feColorMatrix
            type="matrix"
            values="0 0 0 0 0  
                    0 0 0 0 0  
                    0 0 0 0 0  
                    -1 -1 -1 0 1"
          />
        </filter>
      </defs>
      <image
        key={`${config.current_map_path}-${visibility_timestamp}`}
        href={fowUrl}
        x={0}
        y={0}
        width={config.map_width}
        height={config.map_height}
        filter="url(#fow-invert-alpha)"
        style={{ pointerEvents: 'none' }}
      />
    </g>
  );
};
