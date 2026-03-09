import React from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { injectAction } from '../services/api';

export const VisionControl: React.FC = () => {
  const { config } = useSystemState();

  const handleToggleHandMasking = () => {
    injectAction('TOGGLE_HAND_MASKING');
  };

  const handleToggleFow = () => {
    injectAction('TOGGLE_FOW');
  };

  const handleResetFow = () => {
    injectAction('RESET_FOW');
  };

  const handleToggleDebug = () => {
    injectAction('TOGGLE_DEBUG_MODE');
  };

  const handleSetGmPosition = (pos: string) => {
    injectAction('SET_GM_POSITION', pos);
  };

  const gmPositions = [
    'None',
    'North',
    'South',
    'East',
    'West',
    'North West',
    'North East',
    'South West',
    'South East',
  ];

  return (
    <div className="space-y-4 text-black">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-700">Projection Masking</span>
        <button
          onClick={handleToggleHandMasking}
          className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
            config.enable_hand_masking
              ? 'bg-green-100 text-green-800 hover:bg-green-200'
              : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
          }`}
        >
          {config.enable_hand_masking ? 'ENABLED' : 'DISABLED'}
        </button>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-700">Fog of War</span>
        <button
          onClick={handleToggleFow}
          className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
            !config.fow_disabled
              ? 'bg-green-100 text-green-800 hover:bg-green-200'
              : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
          }`}
        >
          {config.fow_disabled ? 'DISABLED' : 'ENABLED'}
        </button>
      </div>

      <button
        onClick={handleResetFow}
        className="w-full bg-orange-50 hover:bg-orange-100 text-orange-700 text-xs font-semibold py-1.5 px-3 rounded border border-orange-200 transition-colors"
      >
        Reset Fog of War
      </button>

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-700">Debug Overlay</span>
        <button
          onClick={handleToggleDebug}
          className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
            config.debug_mode
              ? 'bg-blue-100 text-blue-800 hover:bg-blue-200'
              : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
          }`}
        >
          {config.debug_mode ? 'ON' : 'OFF'}
        </button>
      </div>

      <div className="space-y-1">
        <label className="block text-xs font-medium text-gray-700">GM Position</label>
        <select
          value={config.gm_position}
          onChange={(e) => handleSetGmPosition(e.target.value)}
          className="w-full px-2 py-1 text-sm border rounded focus:ring-blue-500 focus:border-blue-500 bg-white text-black"
        >
          {gmPositions.map((pos) => (
            <option key={pos} value={pos}>
              {pos}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};
