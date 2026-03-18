import React, { useState } from 'react';
import { type Token } from '../types/system';
import { updateToken, injectAction, deleteTokenOverride, deleteToken } from '../services/api';
import { useSystemState } from '../hooks/useSystemState';

interface TokenPropertiesEditorProps {
  token: Partial<Token> & { id: number };
  onUpdate?: () => void;
}

export const TokenPropertiesEditor: React.FC<TokenPropertiesEditorProps> = ({
  token,
  onUpdate,
}) => {
  const { config, maps } = useSystemState();
  const [localName, setLocalName] = useState<string | null>(null);
  const [localColor, setLocalColor] = useState<string | null>(null);
  const [localType, setLocalType] = useState<string | null>(null);
  const [localProfile, setLocalProfile] = useState<string | null>(null);
  const [localSize, setLocalSize] = useState<number | null>(null);
  const [localHeightMm, setLocalHeightMm] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const arucoDefault = config?.aruco_defaults?.[token.id];
  const isOverridden = config?.current_map_path && maps && maps[config.current_map_path]
    ? !!maps[config.current_map_path]?.aruco_overrides?.[token.id]
    : false;

  const [editMode, setEditMode] = useState<'MAP' | 'GLOBAL'>(isOverridden ? 'MAP' : 'GLOBAL');

  const tokenProfile =
    localProfile !== null ? localProfile : (token.profile as string) || arucoDefault?.profile || '';
  const isProfileSelected = tokenProfile !== '' && tokenProfile !== null;
  const profileDef = isProfileSelected ? config?.token_profiles?.[tokenProfile] : null;

  const tokenName =
    localName !== null ? localName : (token.name as string) || arucoDefault?.name || '';
  const tokenColor =
    localColor !== null ? localColor : (token.color as string) || arucoDefault?.color || '';
  const tokenType =
    localType !== null ? localType : (token.type as string) || arucoDefault?.type || 'NPC';

  const handleTokenUpdate = async (update: {
    name?: string;
    color?: string;
    type?: string;
    profile?: string;
    size?: number;
    height_mm?: number;
  }) => {
    try {
      await updateToken(token.id, {
        ...update,
        is_map_override: editMode === 'MAP',
      });
      if (onUpdate) onUpdate();
    } catch (e) {
      console.error(e);
    }
  };

  let tokenSize = 1;
  if (localSize !== null) {
    tokenSize = localSize;
  } else if (isProfileSelected && profileDef) {
    tokenSize = profileDef.size;
  } else if ((token.size as number) !== undefined) {
    tokenSize = token.size as number;
  } else if (arucoDefault?.size !== undefined) {
    tokenSize = arucoDefault.size;
  }

  let tokenHeightMm = 0;
  if (localHeightMm !== null) {
    tokenHeightMm = localHeightMm;
  } else if (isProfileSelected && profileDef) {
    tokenHeightMm = profileDef.height_mm;
  } else if ((token.height_mm as number) !== undefined) {
    tokenHeightMm = token.height_mm as number;
  } else if (arucoDefault?.height_mm !== undefined) {
    tokenHeightMm = arucoDefault.height_mm;
  }

  return (
    <div key={token.id} className="space-y-4 text-black">
      <div className="bg-blue-50 p-3 rounded-md border border-blue-100">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center space-x-2">
              <p className="text-sm font-semibold text-blue-800">
                {tokenName ? `${tokenName} (#${token.id})` : `Token #${token.id}`}
              </p>
              {isOverridden && (
                <span
                  className="px-1.5 py-0.5 bg-yellow-100 text-yellow-800 text-[10px] font-bold rounded border border-yellow-200"
                  title="This token has map-specific overrides"
                >
                  OVERRIDDEN
                </span>
              )}
            </div>
            {token.world_x !== undefined && (
              <p className="text-xs text-blue-600 mt-1">
                Status: {token.is_occluded ? 'Occluded' : 'Visible'}
              </p>
            )}
          </div>
          {tokenColor && (
            <div
              className="w-6 h-6 rounded-full border border-blue-200 shadow-sm"
              style={{ backgroundColor: tokenColor }}
              title={`Color: ${tokenColor}`}
            />
          )}
        </div>
      </div>

      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-tighter">
          Target: {editMode === 'MAP' ? 'Map Override' : 'Global Default'}
        </span>
        <div className="flex bg-gray-100 p-0.5 rounded-md">
          <button
            onClick={() => setEditMode('GLOBAL')}
            className={`px-2 py-0.5 text-[10px] font-bold rounded transition-colors ${
              editMode === 'GLOBAL' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'
            }`}
          >
            GLOBAL
          </button>
          <button
            disabled={!config.current_map_path}
            onClick={() => setEditMode('MAP')}
            className={`px-2 py-0.5 text-[10px] font-bold rounded transition-colors ${
              editMode === 'MAP'
                ? 'bg-white text-orange-600 shadow-sm'
                : 'text-gray-500 disabled:opacity-30'
            }`}
          >
            MAP
          </button>
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
            <label
              htmlFor={`token-name-${token.id}`}
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Name
            </label>
            <input
              id={`token-name-${token.id}`}
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
          <label
            htmlFor={`token-color-${token.id}`}
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            Color
          </label>
          <div className="flex space-x-2">
            <input
              id={`token-color-picker-${token.id}`}
              type="color"
              value={tokenColor.startsWith('#') && tokenColor.length === 7 ? tokenColor : '#ffff00'}
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
              id={`token-color-${token.id}`}
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
              <label
                htmlFor={`token-profile-${token.id}`}
                className="block text-xs font-medium text-gray-700 mb-1"
              >
                Token Profile
              </label>
              {config?.token_profiles ? (
                <select
                  id={`token-profile-${token.id}`}
                  value={tokenProfile}
                  onChange={(e) => {
                    const newProfile = e.target.value;
                    setLocalProfile(newProfile);
                    if (newProfile) {
                      // When selecting a profile, clear individual overrides
                      handleTokenUpdate({
                        profile: newProfile,
                        size: undefined,
                        height_mm: undefined,
                      });
                    } else {
                      handleTokenUpdate({ profile: undefined });
                    }
                  }}
                  className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                >
                  <option value="">Custom (Manual Size)</option>
                  {Object.keys(config.token_profiles).map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={`token-profile-${token.id}`}
                  type="text"
                  value={tokenProfile}
                  onChange={(e) => setLocalProfile(e.target.value)}
                  onBlur={() => {
                    handleTokenUpdate({ profile: tokenProfile || undefined });
                    setLocalProfile(null);
                  }}
                  placeholder="e.g. standard_1in"
                  className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white"
                />
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label
                  htmlFor={`token-size-${token.id}`}
                  className={`block text-xs font-medium mb-1 ${
                    isProfileSelected ? 'text-gray-400' : 'text-gray-700'
                  }`}
                >
                  Size (Grid)
                </label>
                <input
                  id={`token-size-${token.id}`}
                  type="number"
                  value={tokenSize}
                  onChange={(e) => setLocalSize(Number(e.target.value))}
                  onBlur={() => {
                    handleTokenUpdate({ size: tokenSize });
                    setLocalSize(null);
                  }}
                  disabled={isProfileSelected}
                  min={1}
                  className={`w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white ${
                    isProfileSelected ? 'text-gray-400 bg-gray-50' : ''
                  }`}
                />
              </div>
              <div>
                <label
                  htmlFor={`token-height-${token.id}`}
                  className={`block text-xs font-medium mb-1 ${
                    isProfileSelected ? 'text-gray-400' : 'text-gray-700'
                  }`}
                >
                  Height (mm)
                </label>
                <input
                  id={`token-height-${token.id}`}
                  type="number"
                  value={tokenHeightMm}
                  onChange={(e) => setLocalHeightMm(Number(e.target.value))}
                  onBlur={() => {
                    handleTokenUpdate({ height_mm: tokenHeightMm });
                    setLocalHeightMm(null);
                  }}
                  disabled={isProfileSelected}
                  min={0}
                  className={`w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white ${
                    isProfileSelected ? 'text-gray-400 bg-gray-50' : ''
                  }`}
                />
              </div>
            </div>
            {token.world_x !== undefined && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">World X</label>
                  <input
                    type="number"
                    value={Number(token.world_x).toFixed(2)}
                    readOnly
                    className="w-full px-2 py-1 text-sm border rounded bg-gray-50 text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">World Y</label>
                  <input
                    type="number"
                    value={Number(token.world_y).toFixed(2)}
                    readOnly
                    className="w-full px-2 py-1 text-sm border rounded bg-gray-50 text-gray-500"
                  />
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {token.world_x !== undefined && (
        <div className="pt-2 space-y-2">
          <div className="flex space-x-2">
            <button
              onClick={() => injectAction('INSPECT_TOKEN', token.id.toString())}
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
      )}

      {isOverridden && (
        <div className="pt-1">
          <button
            onClick={async () => {
              try {
                await deleteTokenOverride(token.id);
                if (onUpdate) onUpdate();
              } catch (e) {
                console.error(e);
              }
            }}
            className="w-full bg-white hover:bg-red-50 text-red-600 text-[10px] font-bold py-1 px-3 rounded border border-red-200 transition-colors uppercase"
          >
            Reset to Global Default
          </button>
        </div>
      )}

      {arucoDefault && (
        <div className="pt-1">
          <button
            onClick={async () => {
              if (
                window.confirm(
                  `Are you sure you want to delete the GLOBAL definition for Token #${token.id}?`
                )
              ) {
                try {
                  await deleteToken(token.id);
                  if (onUpdate) onUpdate();
                } catch (e) {
                  console.error(e);
                }
              }
            }}
            className="w-full bg-white hover:bg-gray-50 text-gray-400 text-[10px] font-bold py-1 px-3 rounded border border-gray-200 transition-colors uppercase"
          >
            Delete Global Definition
          </button>
        </div>
      )}
    </div>
  );
};
