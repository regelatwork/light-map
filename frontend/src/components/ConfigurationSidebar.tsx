import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { saveGridConfig, injectAction, updateToken } from '../services/api';
import { type Token, SelectionType } from '../types/system';
import { VisionControl } from './VisionControl';

export const ConfigurationSidebar: React.FC = () => {
  const { tokens, world, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
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
    selection.type === SelectionType.TOKEN ? tokens.find((t: Token) => t.id === selection.id) : null;

  const selectedDoor =
    selection.type === SelectionType.DOOR
      ? world.blockers?.find((b) => b.id === selection.id)
      : null;

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

        {/* Vision Control */}
        <section>
          <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            Vision & Display
          </h3>
          <VisionControl />
        </section>

        <hr className="border-gray-200" />

        {/* Selected Entity */}
        <section>
          <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            Selection Properties
          </h3>

          {!selectedToken && !selectedDoor && (
            <div className="text-sm text-gray-400 italic p-4 text-center border-2 border-dashed rounded-md">
              Select a token or door on the canvas to view its properties
            </div>
          )}

          {selectedToken && (
            <div key={selectedToken.id} className="space-y-4 text-black">
              <div className="bg-blue-50 p-3 rounded-md border border-blue-100">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-semibold text-blue-800">
                      {selectedToken.name ? `${selectedToken.name} (#${selectedToken.id})` : `Token #${selectedToken.id}`}
                    </p>
                    <p className="text-xs text-blue-600 mt-1">
                      Status: {selectedToken.is_occluded ? 'Occluded' : 'Visible'}
                    </p>
                  </div>
                  {selectedToken.color && (
                    <div 
                      className="w-6 h-6 rounded-full border border-blue-200 shadow-sm"
                      style={{ backgroundColor: selectedToken.color }}
                      title={`Color: ${selectedToken.color}`}
                    />
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
                  <input
                    type="text"
                    defaultValue={selectedToken.name as string || ''}
                    onBlur={(e) => updateToken(selectedToken.id, { name: e.target.value })}
                    className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Color</label>
                  <input
                    type="text"
                    defaultValue={selectedToken.color as string || ''}
                    placeholder="#RRGGBB or css color"
                    onBlur={(e) => updateToken(selectedToken.id, { color: e.target.value })}
                    className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                  />
                </div>
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

              <div className="pt-2 space-y-2">
                <div className="flex space-x-2">
                  <button
                    onClick={() => injectAction('INSPECT_TOKEN', selectedToken.id.toString())}
                    className="flex-1 bg-purple-100 hover:bg-purple-200 text-purple-800 text-xs font-semibold py-1.5 px-3 rounded border border-purple-300 transition-colors"
                  >
                    Inspect Vision
                  </button>
                  <button
                    onClick={() => injectAction('CLEAR_INSPECTION')}
                    className="bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-semibold py-1.5 px-3 rounded border border-gray-300 transition-colors"
                  >
                    Clear Vision
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedDoor && (
            <div className="space-y-4 text-black">
              <div className="bg-yellow-50 p-3 rounded-md border border-yellow-200">
                <p className="text-sm font-semibold text-yellow-800">Door: {selectedDoor.id}</p>
                <p className="text-xs text-yellow-600 mt-1">
                  Status: {selectedDoor.is_open ? 'Open' : 'Closed'}
                </p>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => injectAction('TOGGLE_DOOR', selectedDoor.id)}
                  className="w-full bg-yellow-100 hover:bg-yellow-200 text-yellow-800 text-xs font-semibold py-1.5 px-3 rounded border border-yellow-300 transition-colors"
                >
                  {selectedDoor.is_open ? 'Close Door' : 'Open Door'}
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </aside>
  );
};
