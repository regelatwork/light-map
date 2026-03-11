import React from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { MenuActions, SelectionType, VisibilityType } from '../types/system';
import { useSelection } from './SelectionContext';
import { injectAction } from '../services/api';

export const DoorLayer: React.FC = () => {
  const { world, grid_spacing_svg, isConnected } = useSystemState();
  const { selection, setSelection } = useSelection();

  if (!isConnected || !world.blockers || world.blockers.length === 0) {
    return null;
  }

  // Styles matching Python DoorLayer.py
  const spacing = grid_spacing_svg || 10;
  const baseWallThickness = spacing / 16.0;
  const yellowThickness = Math.max(2, baseWallThickness * 3.0);
  const padding = Math.max(2, 2.0 * baseWallThickness);
  const blackThickness = yellowThickness + padding;

  const circleRadius = Math.max(3, yellowThickness * 0.8);
  const circleOutline = circleRadius + Math.max(2, padding / 2);

  const YELLOW = '#FFFF00';
  const BLACK = '#000000';
  const HIGHLIGHT = '#3b82f6'; // Blue-500

  const handleDoorClick = (e: React.MouseEvent, doorId: string) => {
    e.stopPropagation();
    setSelection({ type: SelectionType.DOOR, id: doorId });
    injectAction(MenuActions.TOGGLE_DOOR, doorId).catch(console.error);
  };

  return (
    <g id="door-layer">
      {world.blockers
        .filter((b) => b.type === VisibilityType.DOOR)
        .map((door) => {
          if (door.points.length < 2) return null;
          const isSelected = selection.type === SelectionType.DOOR && selection.id === door.id;

          if (door.is_open) {
            const endpoints = [door.points[0], door.points[door.points.length - 1]];
            return (
              <g
                key={`door-${door.id}`}
                onClick={(e) => handleDoorClick(e, door.id)}
                className="cursor-pointer"
              >
                {endpoints.map((pt, i) => (
                  <g key={`pt-${i}`}>
                    {isSelected && (
                      <circle
                        cx={pt[0]}
                        cy={pt[1]}
                        r={circleOutline + 3}
                        fill="none"
                        stroke={HIGHLIGHT}
                        strokeWidth="3"
                        className="opacity-75 animate-pulse"
                      />
                    )}
                    <circle cx={pt[0]} cy={pt[1]} r={circleOutline} fill={BLACK} />
                    <circle cx={pt[0]} cy={pt[1]} r={circleRadius} fill={YELLOW} />
                  </g>
                ))}
              </g>
            );
          } else {
            const pointsStr = door.points.map((p) => `${p[0]},${p[1]}`).join(' ');
            return (
              <g
                key={`door-${door.id}`}
                onClick={(e) => handleDoorClick(e, door.id)}
                className="cursor-pointer"
              >
                {isSelected && (
                  <polyline
                    points={pointsStr}
                    fill="none"
                    stroke={HIGHLIGHT}
                    strokeWidth={blackThickness + 6}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    className="opacity-50 animate-pulse"
                  />
                )}
                <polyline
                  points={pointsStr}
                  fill="none"
                  stroke={BLACK}
                  strokeWidth={blackThickness}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                <polyline
                  points={pointsStr}
                  fill="none"
                  stroke={YELLOW}
                  strokeWidth={yellowThickness}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              </g>
            );
          }
        })}
    </g>
  );
};
