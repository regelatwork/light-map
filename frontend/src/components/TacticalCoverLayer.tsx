import React from 'react';
import { useTacticalCover } from '../hooks/useTacticalCover';
import { useSystemState } from '../hooks/useSystemState';

/**
 * Renders tactical cover information (vision wedges and bonuses) on the schematic canvas.
 * This is a GM-only layer that pulls data on demand.
 */
export const TacticalCoverLayer: React.FC = () => {
  const { tokens, isConnected, grid_spacing_svg } = useSystemState();
  const { bonuses, attackerId } = useTacticalCover();

  if (!isConnected || !attackerId) {
    return null;
  }

  const attacker = tokens.find((t) => t.id === attackerId);
  if (!attacker) return null;

  // The mask-to-world scale is inverse of world-to-mask scale used in the engine.
  // Engine: svg_to_mask_scale = grid_spacing_svg / 16.0
  const spacing = grid_spacing_svg || 16.0;
  const maskToSvgScale = 16.0 / spacing;

  return (
    <g className="tactical-cover-layer">
      {/* Radar Wedges */}
      {Object.entries(bonuses).map(([targetIdStr, cover]) => {
        const targetId = parseInt(targetIdStr);
        const target = tokens.find((t) => t.id === targetId);
        if (!target) return null;

        const pApex = {
          x: cover.best_apex[0] * maskToSvgScale,
          y: cover.best_apex[1] * maskToSvgScale,
        };

        return (
          <g key={`radar-${targetId}`} style={{ pointerEvents: 'none' }}>
            {cover.segments && cover.segments.map((seg, idx) => {
              const pStart = {
                x: cover.npc_pixels[seg.start_idx][0] * maskToSvgScale,
                y: cover.npc_pixels[seg.start_idx][1] * maskToSvgScale,
              };
              const pEnd = {
                x: cover.npc_pixels[seg.end_idx][0] * maskToSvgScale,
                y: cover.npc_pixels[seg.end_idx][1] * maskToSvgScale,
              };

              // Path from Apex to start of wedge, then to end of wedge, and back to Apex
              const d = `M ${pApex.x} ${pApex.y} L ${pStart.x} ${pStart.y} L ${pEnd.x} ${pEnd.y} Z`;

              // Colors based on status (0: Clear, 2: Obscured, 3: Soft Cover)
              let fill = 'rgba(59, 130, 246, 0.1)'; // Default blue tint
              let stroke = 'rgba(59, 130, 246, 0.3)';
              
              if (seg.status === 2) { // Obscured
                fill = 'rgba(234, 179, 8, 0.15)'; // Yellow tint
                stroke = 'rgba(234, 179, 8, 0.4)';
              } else if (seg.status === 3) { // Soft Cover
                fill = 'rgba(168, 85, 247, 0.1)'; // Purple tint
                stroke = 'rgba(168, 85, 247, 0.3)';
              }

              return (
                <path
                  key={`seg-${targetId}-${idx}`}
                  d={d}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth="0.5"
                />
              );
            })}

            {/* Bonus Label */}
            <g transform={`translate(${target.world_x}, ${target.world_y + 22})`}>
              <rect
                x="-22"
                y="-7"
                width="44"
                height="14"
                rx="3"
                fill="white"
                fillOpacity="0.9"
                stroke={cover.ac_bonus > 0 ? '#1e40af' : '#6b7280'}
                strokeWidth="0.5"
                className="drop-shadow-sm"
              />
              <text
                textAnchor="middle"
                dominantBaseline="middle"
                className={`text-[9px] font-bold select-none ${
                  cover.ac_bonus > 0 ? 'fill-blue-800' : 'fill-gray-600'
                }`}
              >
                {cover.ac_bonus === -1 ? 'TOTAL' : `+${cover.ac_bonus} AC`}
              </text>
            </g>

            {/* Interaction Area for Tooltip */}
            <circle
              cx={target.world_x}
              cy={target.world_y}
              r="15"
              fill="transparent"
              style={{ pointerEvents: 'auto' }}
              className="cursor-help"
            >
              <title>{cover.explanation}</title>
            </circle>
          </g>
        );
      })}
    </g>
  );
};
