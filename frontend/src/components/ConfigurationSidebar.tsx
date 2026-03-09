import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { saveGridConfig } from '../services/api';
import type { Token } from '../types/system';

export const ConfigurationSidebar: React.FC = () => {
  const { tokens, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
  const { selection } = useSelection();

  const [localGridX, setLocalGridX] = useState<number | null>(null);
  const [localGridY, setLocalGridY] = useState<number | null>(null);

  const gridX = localGridX !== null ? localGridX : grid_origin_svg_x || 0;
  const gridY = localGridY !== null ? localGridY : grid_origin_svg_y || 0;

  const handleGridSave = async () => {
    try {
      await saveGridConfig(gridX, gridY);
      setLocalGridX(null);
      setLocalGridY(null);
    } catch (e) {
      console.error(e);
    }
  };

  const selectedToken =
    selection.type === 'token' ? tokens.find((t: Token) => t.id === selection.id) : null;

  return (
    <aside className="w-80 bg-white shadow-md flex flex-col border-l border-gray-200 z-10">
      <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
        <h2 className="font-semibold text-gray-800">Configuration</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* System Settings */}
        <section>
          <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            System Settings
          </h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Grid Origin X</label>
              <input
                type="number"
                value={gridX}
                onChange={(e) => setLocalGridX(Number(e.target.value))}
                className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white text-black"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Grid Origin Y</label>
              <input
                type="number"
                value={gridY}
                onChange={(e) => setLocalGridY(Number(e.target.value))}
                className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white text-black"
              />
            </div>
            <button
              onClick={handleGridSave}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold py-1.5 px-3 rounded transition-colors"
            >
              Update Grid
            </button>
          </div>
        </section>

        <hr className="border-gray-200" />

        {/* Selected Entity */}
        <section>
          <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            Selection Properties
          </h3>

          {!selectedToken && (
            <div className="text-sm text-gray-400 italic p-4 text-center border-2 border-dashed rounded-md">
              Select a token on the canvas to view its properties
            </div>
          )}

          {selectedToken && (
            <div className="space-y-4 text-black">
              <div className="bg-blue-50 p-3 rounded-md border border-blue-100">
                <p className="text-sm font-semibold text-blue-800">Token #{selectedToken.id}</p>
                <p className="text-xs text-blue-600 mt-1">
                  Status: {selectedToken.is_occluded ? 'Occluded' : 'Visible'}
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">World X</label>
                  <input
                    type="number"
                    value={Number(selectedToken.world_x).toFixed(2)}
                    readOnly
                    className="w-full px-2 py-1 text-sm border rounded bg-gray-50 text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">World Y</label>
                  <input
                    type="number"
                    value={Number(selectedToken.world_y).toFixed(2)}
                    readOnly
                    className="w-full px-2 py-1 text-sm border rounded bg-gray-50 text-gray-500"
                  />
                </div>
              </div>

              <div className="pt-2">
                <p className="text-xs text-gray-500">
                  <em>
                    Note: Editing token properties (name, color) via API is pending backend support.
                  </em>
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </aside>
  );
};
