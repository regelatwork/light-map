import React from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const TokenLayer: React.FC = () => {
  const { tokens, isConnected } = useSystemState();

  if (!isConnected) {
    return null;
  }

  return (
    <g>
      {tokens.map((token) => (
        <g key={token.id} transform={`translate(${token.world_x}, ${token.world_y})`}>
          {/* Token base */}
          <circle
            r="15"
            fill="#ef4444"
            stroke="#b91c1c"
            strokeWidth="2"
            className="drop-shadow-sm"
          />
          {/* Token label */}
          <text
            y="-20"
            textAnchor="middle"
            className="fill-gray-700 font-bold text-xs select-none"
          >
            {token.id}
          </text>
        </g>
      ))}
    </g>
  );
};
