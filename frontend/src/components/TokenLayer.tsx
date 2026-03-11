import React from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { SelectionType } from '../types/system';

export const TokenLayer: React.FC = () => {
  const { tokens, isConnected } = useSystemState();
  const { selection, setSelection } = useSelection();

  if (!isConnected) {
    return null;
  }

  return (
    <g>
      {tokens.map((token) => {
        const isSelected = selection.type === SelectionType.TOKEN && selection.id === token.id;
        return (
          <g
            key={token.id}
            transform={`translate(${token.world_x}, ${token.world_y})`}
            onClick={(e) => {
              e.stopPropagation(); // prevent canvas click from clearing
              setSelection({ type: SelectionType.TOKEN, id: token.id });
            }}
            className="cursor-pointer"
          >
            {/* Selection Highlight */}
            {isSelected && (
              <circle
                r="20"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="3"
                className="opacity-75 animate-pulse"
              />
            )}
            {/* Token base */}
            <circle
              r="15"
              fill={token.is_occluded ? '#9ca3af' : '#ef4444'}
              stroke={isSelected ? '#1d4ed8' : '#b91c1c'}
              strokeWidth={isSelected ? '3' : '2'}
              className="drop-shadow-sm transition-colors duration-200"
            />
            {/* Token label */}
            <text
              y="-20"
              textAnchor="middle"
              className="fill-gray-700 font-bold text-xs select-none pointer-events-none"
            >
              {token.id}
            </text>
          </g>
        );
      })}
    </g>
  );
};
