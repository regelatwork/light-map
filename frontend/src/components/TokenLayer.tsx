import React from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { SelectionType } from '../types/system';

export const TokenLayer: React.FC = () => {
  const { tokens, isConnected, world } = useSystemState();
  const { selection, setSelection } = useSelection();

  if (!isConnected || world.effective_show_tokens === false) {
    return null;
  }

  return (
    <g>
      {tokens.map((token) => {
        const isSelected = selection.type === SelectionType.TOKEN && selection.id === token.id;
        const isNpc = token.type === 'NPC';

        return (
          <g
            key={token.id}
            data-testid={`token-group-${token.id}`}
            transform={`translate(${token.world_x}, ${token.world_y})`}
            onClick={(e) => {
              e.stopPropagation(); // prevent canvas click from clearing
              setSelection({ type: SelectionType.TOKEN, id: token.id });
            }}
            className="cursor-pointer"
          >
            {/* Selection Highlight */}
            {isSelected &&
              (isNpc ? (
                <rect
                  x="-20"
                  y="-20"
                  width="40"
                  height="40"
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="3"
                  className="opacity-75 animate-pulse"
                />
              ) : (
                <circle
                  r="20"
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="3"
                  className="opacity-75 animate-pulse"
                />
              ))}
            {/* Token base */}
            {isNpc ? (
              <rect
                x="-15"
                y="-15"
                width="30"
                height="30"
                fill={token.is_occluded ? '#9ca3af' : token.color || '#ef4444'}
                stroke={isSelected ? '#3b82f6' : '#1d4ed8'}
                strokeWidth={isSelected ? '3' : '2'}
                className="drop-shadow-sm transition-colors duration-200"
              />
            ) : (
              <circle
                r="15"
                fill={token.is_occluded ? '#9ca3af' : token.color || '#ef4444'}
                stroke={isSelected ? '#3b82f6' : '#1d4ed8'}
                strokeWidth={isSelected ? '3' : '2'}
                className="drop-shadow-sm transition-colors duration-200"
              />
            )}
            {/* Token label */}
            <text
              y="-20"
              textAnchor="middle"
              data-testid={`token-label-${token.id}`}
              className="fill-gray-700 font-bold text-xs select-none pointer-events-none"
            >
              {token.name || `#${token.id}`}
            </text>
          </g>
        );
      })}
    </g>
  );
};
