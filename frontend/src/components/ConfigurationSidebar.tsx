import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useSelection } from './SelectionContext';
import { useGridEdit } from './GridEditContext';
import { saveGridConfig, injectAction, updateToken } from '../services/api';
import { type Token, SelectionType } from '../types/system';
import { VisionControl } from './VisionControl';

export const ConfigurationSidebar: React.FC = () => {
  const { tokens, world, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
  const { selection } = useSelection();
  const { isGridEditMode, setIsGridEditMode } = useGridEdit();

  const selectedToken =
    selection.type === SelectionType.TOKEN
      ? tokens.find((t: Token) => t.id === selection.id)
      : null;

  const selectedDoor =
    selection.type === SelectionType.DOOR
      ? world.blockers?.find((b) => b.id === selection.id)
      : null;

  const [localName, setLocalName] = useState<string | null>(null);
  const [localColor, setLocalColor] = useState<string | null>(null);
  const [localType, setLocalType] = useState<string | null>(null);
  const [localProfile, setLocalProfile] = useState<string | null>(null);
  const [localSize, setLocalSize] = useState<number | null>(null);
  const [localHeightMm, setLocalHeightMm] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  React.useEffect(() => {
    setLocalName(null);
    setLocalColor(null);
    setLocalType(null);
    setLocalProfile(null);
    setLocalSize(null);
    setLocalHeightMm(null);
  }, [selectedToken?.id]);

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

  const tokenName = localName !== null ? localName : (selectedToken?.name as string) || '';
  const tokenColor = localColor !== null ? localColor : (selectedToken?.color as string) || '';
  const tokenType = localType !== null ? localType : (selectedToken?.type as string) || 'NPC';
  const tokenProfile =
    localProfile !== null ? localProfile : (selectedToken?.profile as string) || '';
  const tokenSize = localSize !== null ? localSize : (selectedToken?.size as number) || 1;
  const tokenHeightMm =
    localHeightMm !== null ? localHeightMm : (selectedToken?.height_mm as number) || 0;

  const handleTokenUpdate = async (update: {
    name?: string;
    color?: string;
    type?: string;
    profile?: string;
    size?: number;
    height_mm?: number;
  }) => {
    if (!selectedToken) return;
    try {
      await updateToken(selectedToken.id, update);
    } catch (e) {
      console.error(e);
    }
  };

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
                      {selectedToken.name
                        ? `${selectedToken.name} (#${selectedToken.id})`
                        : `Token #${selectedToken.id}`}
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
                <div className="flex items-center space-x-4">
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
                    <div className="flex rounded-md shadow-sm">
                      <button
                        onClick={() => {
                          setLocalType('NPC');
                          handleTokenUpdate({ type: 'NPC' });
                        }}
                        className={`flex-1 px-2 py-1 text-[10px] font-bold border rounded-l-md transition-colors ${
                          tokenType === 'NPC'
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        NPC
                      </button>
                      <button
                        onClick={() => {
                          setLocalType('PC');
                          handleTokenUpdate({ type: 'PC' });
                        }}
                        className={`flex-1 px-2 py-1 text-[10px] font-bold border-t border-b border-r rounded-r-md transition-colors ${
                          tokenType === 'PC'
                            ? 'bg-green-600 text-white border-green-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        PC
                      </button>
                    </div>
                  </div>
                  <div className="flex-1">
                    <label htmlFor="token-name" className="block text-xs font-medium text-gray-700 mb-1">Name</label>
                    <input
                      id="token-name"
                      type="text"
                      value={tokenName}
                      onChange={(e) => setLocalName(e.target.value)}
                      onBlur={() => {
                        handleTokenUpdate({ name: tokenName });
                        setLocalName(null);
                      }}
                      className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                    />
                  </div>
                </div>
                <div>
                  <label htmlFor="token-color" className="block text-xs font-medium text-gray-700 mb-1">Color</label>
                  <div className="flex space-x-2">
                    <input
                      id="token-color-picker"
                      type="color"
                      value={
                        tokenColor.startsWith('#') && tokenColor.length === 7
                          ? tokenColor
                          : '#ffff00'
                      }
                      onChange={(e) => {
                        const newColor = e.target.value;
                        setLocalColor(newColor);
                        handleTokenUpdate({ color: newColor });
                      }}
                      className="w-8 h-8 p-0.5 border rounded cursor-pointer bg-white shadow-sm"
                      title="Pick a color"
                      style={{ direction: 'rtl' }}
                    />
                    <input
                      id="token-color"
                      type="text"
                      value={tokenColor}
                      onChange={(e) => setLocalColor(e.target.value)}
                      onBlur={() => {
                        handleTokenUpdate({ color: tokenColor });
                        setLocalColor(null);
                      }}
                      placeholder="#RRGGBB or css color"
                      className="flex-1 px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                    />
                  </div>
                </div>
                <div className="flex items-center pt-1">
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-[10px] text-gray-400 hover:text-gray-600 uppercase tracking-tighter font-bold flex items-center"
                  >
                    {showAdvanced ? 'Hide' : 'Show'} Advanced Properties
                    <svg
                      className={`ml-1 h-3 w-3 transform transition-transform ${
                        showAdvanced ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </button>
                </div>

                {showAdvanced && (
                  <div className="space-y-3 pt-2 border-t border-gray-100">
                    <div>
                      <label htmlFor="token-profile" className="block text-xs font-medium text-gray-700 mb-1">
                        Token Profile
                      </label>
                      <input
                        id="token-profile"
                        type="text"
                        value={tokenProfile}
                        onChange={(e) => setLocalProfile(e.target.value)}
                        onBlur={() => {
                          handleTokenUpdate({ profile: tokenProfile });
                          setLocalProfile(null);
                        }}
                        placeholder="e.g. standard_1in"
                        className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label htmlFor="token-size" className="block text-xs font-medium text-gray-700 mb-1">
                          Size (Grid)
                        </label>
                        <input
                          id="token-size"
                          type="number"
                          value={tokenSize}
                          onChange={(e) => setLocalSize(Number(e.target.value))}
                          onBlur={() => {
                            handleTokenUpdate({ size: tokenSize });
                            setLocalSize(null);
                          }}
                          min={1}
                          className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                        />
                      </div>
                      <div>
                        <label htmlFor="token-height" className="block text-xs font-medium text-gray-700 mb-1">
                          Height (mm)
                        </label>
                        <input
                          id="token-height"
                          type="number"
                          value={tokenHeightMm}
                          onChange={(e) => setLocalHeightMm(Number(e.target.value))}
                          onBlur={() => {
                            handleTokenUpdate({ height_mm: tokenHeightMm });
                            setLocalHeightMm(null);
                          }}
                          min={0}
                          className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        World X
                      </label>
                      <input
                        type="number"
                        value={Number(selectedToken.world_x).toFixed(2)}
                        readOnly
                        className="w-full px-2 py-1 text-sm border rounded bg-gray-50 text-gray-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        World Y
                      </label>
                      <input
                        type="number"
                        value={Number(selectedToken.world_y).toFixed(2)}
                        readOnly
                        className="w-full px-2 py-1 text-sm border rounded bg-gray-50 text-gray-500"
                      />
                    </div>
                  </div>
                )}
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
