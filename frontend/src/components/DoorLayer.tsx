import React from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const DoorLayer: React.FC = () => {
  const { world, grid_spacing_svg, isConnected } = useSystemState();

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

  return (
    <g id="door-layer">
      {world.blockers
        .filter((b) => b.type === 'DOOR')
        .map((door) => {
          if (door.points.length < 2) return null;

          if (door.is_open) {
            return (
              <g key={`door-${door.id}`}>
                {door.points.map((pt, i) => (
                  <g key={`pt-${i}`}>
                    <circle cx={pt[0]} cy={pt[1]} r={circleOutline} fill={BLACK} />
                    <circle cx={pt[0]} cy={pt[1]} r={circleRadius} fill={YELLOW} />
                  </g>
                ))}
              </g>
            );
          } else {
            const pointsStr = door.points.map((p) => `${p[0]},${p[1]}`).join(' ');
            return (
              <g key={`door-${door.id}`}>
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
