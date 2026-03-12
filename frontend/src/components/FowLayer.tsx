import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const FowLayer: React.FC = () => {
  const { config, isConnected, visibility_timestamp } = useSystemState();
  const [errorId, setErrorId] = useState<string | null>(null);

  const currentId = `${config.current_map_path}-${visibility_timestamp}`;
  const hasError = errorId === currentId;

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
      {!hasError ? (
        <image
          key={currentId}
          href={fowUrl}
          x={0}
          y={0}
          width={config.map_width}
          height={config.map_height}
          filter="url(#fow-invert-alpha)"
          style={{ pointerEvents: 'none' }}
          onError={() => setErrorId(currentId)}
          data-testid="fow-image"
        />
      ) : (
        <text
          x={config.map_width / 2}
          y={config.map_height / 2 + 40}
          textAnchor="middle"
          fill="#ef4444"
          className="text-sm font-bold select-none"
          style={{ pointerEvents: 'none' }}
        >
          Fog-of-war mask failed to load
        </text>
      )}
    </g>
  );
};
