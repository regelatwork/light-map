import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { useGridEdit } from './GridEditContext';
import { SelectionType } from '../types/system';
import { TokenPropertiesEditor } from './TokenPropertiesEditor';
import { injectAction, saveGridConfig } from '../services/api';

export const ConfigurationSidebar: React.FC = () => {
  const { tokens, world, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
  const { selection, setSelection } = useSelection();
  const { isGridEditMode, setIsGridEditMode } = useGridEdit();

  // If a token is selected on map, use its ID. Otherwise use manual entry.
  const activeTokenId = selection.type === SelectionType.TOKEN ? selection.id : null;

  const selectedDoor =
    selection.type === SelectionType.DOOR
      ? world.blockers?.find((b) => b.id === selection.id)
      : null;

  const [manualArUcoId, setManualArUcoId] = useState<string>('');

  // Local state for grid inputs in sidebar
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

  // Synchronize manual ID field with selection
  const lastSyncedId = useRef<string | null>(null);
  useLayoutEffect(() => {
    const newId = activeTokenId !== null ? activeTokenId.toString() : '';
    if (newId !== lastSyncedId.current) {
      lastSyncedId.current = newId;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setManualArUcoId(newId);
    }
  }, [activeTokenId]);

  useEffect(() => {
    console.debug('Selection changed:', selection);
  }, [selection]);

  const displayId = activeTokenId !== null ? activeTokenId : parseInt(manualArUcoId);
  const activeToken =
    selection.type === SelectionType.TOKEN && !isNaN(Number(displayId))
      ? tokens?.find((t) => t.id === Number(displayId)) || { id: Number(displayId) }
      : null;

  return (
    <aside className="w-80 bg-white shadow-md flex flex-col border-l border-gray-200 z-10 text-black">
      <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
        <h2 className="font-semibold text-gray-800">Entity Properties</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* System Controls */}
        <section className="bg-blue-50 -mx-4 px-4 py-4 border-b border-blue-100 mb-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h4 className="text-xs font-bold text-blue-800 uppercase tracking-wider">Visual Grid Editor</h4>
              <p className="text-[10px] text-blue-600 font-medium">Toggle handles on map</p>
            </div>
            <button
              onClick={() => setIsGridEditMode(!isGridEditMode)}
              aria-label="Visual Grid Editor"
              className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none shadow-sm ${
                isGridEditMode ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  isGridEditMode ? 'translate-x-5.5' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {isGridEditMode && (
            <div className="grid grid-cols-2 gap-3 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="space-y-1">
                <label htmlFor="grid-origin-x" className="block text-[10px] font-bold text-blue-700 uppercase">Origin X</label>
                <input
                  id="grid-origin-x"
                  type="number"
                  value={Math.round(gridX)}
                  onChange={(e) => setLocalGridX(Number(e.target.value))}
                  onBlur={handleGridSave}
                  className="w-full px-2 py-1 text-xs border rounded bg-white font-mono"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="grid-origin-y" className="block text-[10px] font-bold text-blue-700 uppercase">Origin Y</label>
                <input
                  id="grid-origin-y"
                  type="number"
                  value={Math.round(gridY)}
                  onChange={(e) => setLocalGridY(Number(e.target.value))}
                  onBlur={handleGridSave}
                  className="w-full px-2 py-1 text-xs border rounded bg-white font-mono"
                />
              </div>
              <div className="col-span-2 text-[10px] text-blue-600 bg-blue-100 bg-opacity-30 p-2 rounded flex gap-2">
                <p>Use <span className="font-bold text-green-700">Green Handle</span> to move origin, <span className="font-bold text-blue-700">Blue Handles</span> for scale.</p>
              </div>
            </div>
          )}
        </section>

        {/* Entity Properties */}
        <section>
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
                      setSelection({ type: SelectionType.TOKEN, id: idNum.toString() });
                    } else if (val === '') {
                      setSelection({ type: SelectionType.NONE, id: '' });
                    }
                  }}
                  className="w-full px-3 py-2 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white text-black"
                  placeholder="ID (e.g. 12)"
                />
                <datalist id="known-aruco-ids">
                  {tokens?.map((t) => (
                    <option key={t.id} value={t.id}>
                      Marker {t.id}
                    </option>
                  ))}
                </datalist>
              </div>
              {manualArUcoId && (
                <button
                  onClick={() => {
                    setManualArUcoId('');
                    setSelection({ type: SelectionType.NONE, id: '' });
                  }}
                  className="px-2 py-1 text-xs text-gray-500 hover:text-red-600 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {selectedDoor ? (
            <div className="p-4 bg-orange-50 rounded-lg border border-orange-100 animate-in fade-in duration-300">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-2 bg-orange-100 rounded-lg text-orange-700">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <h4 className="font-bold text-gray-800">Door Selected</h4>
              </div>
              <p className="text-xs text-gray-600 mb-4">
                ID: <span className="font-mono font-bold text-orange-700">{selectedDoor.id}</span>
              </p>
              <div className="space-y-2">
                <button
                  onClick={() => injectAction('TOGGLE_DOOR', selectedDoor.id)}
                  className="w-full py-2 bg-orange-600 text-white rounded-lg font-bold text-xs hover:bg-orange-700 transition-all shadow-sm active:scale-95"
                >
                  Toggle Open/Closed
                </button>
                <button
                  onClick={() => setSelection({ type: SelectionType.NONE, id: '' })}
                  className="w-full py-2 bg-white text-gray-500 rounded-lg font-bold text-xs hover:bg-gray-100 transition-all"
                >
                  Deselect
                </button>
              </div>
            </div>
          ) : activeToken ? (
            <div className="animate-in fade-in duration-300">
              <TokenPropertiesEditor token={activeToken} />
            </div>
          ) : (
            <div className="py-12 flex flex-col items-center justify-center text-center px-4">
              <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4 border border-gray-100">
                <svg
                  className="w-8 h-8 text-gray-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-gray-400">
                Select a token or door on the map to view properties.
              </p>
            </div>
          )}
        </section>
      </div>

      {/* Selected Entity Summary Footer */}
      {(activeToken || selectedDoor) && (
        <div className="p-4 border-t bg-gray-50 text-[10px] text-gray-400 flex justify-between items-center">
          <span>Active Selection</span>
          <span className="font-mono text-blue-600 font-bold">
            {activeToken ? `Marker ${activeToken.id}` : selectedDoor?.id}
          </span>
        </div>
      )}
    </aside>
  );
};
