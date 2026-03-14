import React, { useState, useEffect } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { useGridEdit } from './GridEditContext';
import { saveGridConfig, injectAction } from '../services/api';
import { SelectionType } from '../types/system';
import { VisionControl } from './VisionControl';
import { TokenPropertiesEditor } from './TokenPropertiesEditor';

export const ConfigurationSidebar: React.FC = () => {
  const { tokens, world, config, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
  const { selection, setSelection } = useSelection();
  const { isGridEditMode, setIsGridEditMode } = useGridEdit();

  // If a token is selected on map, use its ID. Otherwise use manual entry.
  const activeTokenId = selection.type === SelectionType.TOKEN ? selection.id : null;

  const selectedDoor =
    selection.type === SelectionType.DOOR
      ? world.blockers?.find((b) => b.id === selection.id)
      : null;

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

  const [manualArUcoId, setManualArUcoId] = useState<string>('');

  // Synchronize manual ID field with selection
  useEffect(() => {
    if (activeTokenId !== null) {
      setManualArUcoId(activeTokenId.toString());
    }
  }, [activeTokenId]);

  const displayId = activeTokenId !== null ? activeTokenId : parseInt(manualArUcoId);
  const activeToken = !isNaN(Number(displayId))
    ? tokens.find((t) => t.id === Number(displayId)) || { id: Number(displayId) }
    : null;

  return (
    <aside className="w-80 bg-white shadow-md flex flex-col border-l border-gray-200 z-10 text-black">
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
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-700">Edit Grid Visuals</span>
              <button
                onClick={() => setIsGridEditMode(!isGridEditMode)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
                  isGridEditMode ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                    isGridEditMode ? 'translate-x-5' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {isGridEditMode && (
              <div className="p-2 bg-blue-50 rounded border border-blue-100 space-y-2">
                <p className="text-[10px] text-blue-700 leading-tight">
                  Drag the <span className="font-bold text-green-600">Green Handle</span> to move
                  the origin.
                  <br />
                  Drag the <span className="font-bold text-blue-600">Blue Handle</span> to adjust
                  spacing.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] text-gray-500 uppercase">X</label>
                    <input
                      type="number"
                      value={Math.round(gridX)}
                      onChange={(e) => setLocalGridX(Number(e.target.value))}
                      onBlur={handleGridSave}
                      className="w-full px-1 py-0.5 text-xs border rounded bg-white text-black"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-gray-500 uppercase">Y</label>
                    <input
                      type="number"
                      value={Math.round(gridY)}
                      onChange={(e) => setLocalGridY(Number(e.target.value))}
                      onBlur={handleGridSave}
                      className="w-full px-1 py-0.5 text-xs border rounded bg-white text-black"
                    />
                  </div>
                </div>
              </div>
            )}
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

        {/* Entity Properties */}
        <section>
          <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            Entity Properties
          </h3>

          <div className="mb-4">
            <label className="block text-[10px] font-bold text-gray-400 uppercase mb-1">
              Select Token by ArUco ID
            </label>
            <div className="flex space-x-2">
              <div className="flex-1 relative">
                <input
                  list="known-aruco-ids"
                  type="number"
                  value={manualArUcoId}
                  onChange={(e) => {
                    const val = e.target.value;
                    setManualArUcoId(val);
                    const idNum = parseInt(val);
                    if (!isNaN(idNum)) {
                      setSelection({ type: SelectionType.TOKEN, id: idNum });
                    } else {
                      setSelection({ type: SelectionType.NONE, id: null });
                    }
                  }}
                  placeholder="Enter or select ID..."
                  className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white text-black"
                />
                <datalist id="known-aruco-ids">
                  {Object.entries(config.aruco_defaults || {}).map(([id, def]) => (
                    <option key={id} value={id}>
                      {def.name}
                    </option>
                  ))}
                </datalist>
              </div>
              {manualArUcoId && (
                <button
                  onClick={() => {
                    setManualArUcoId('');
                    setSelection({ type: SelectionType.NONE, id: null });
                  }}
                  className="px-2 py-1 text-[10px] font-bold text-gray-400 hover:text-gray-600 uppercase"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {!activeToken && !selectedDoor && (
            <div className="text-sm text-gray-400 italic p-4 text-center border-2 border-dashed rounded-md">
              Select a token or door on the canvas, or enter an ArUco ID to view properties
            </div>
          )}

          {activeToken && (
            <div className="mt-2">
              <TokenPropertiesEditor token={activeToken} key={`token-${activeToken.id}`} />
            </div>
          )}

          {selectedDoor && (
            <div className="space-y-4 text-black border-t border-gray-100 pt-4 mt-4">
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
