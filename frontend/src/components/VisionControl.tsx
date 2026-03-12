import { type FC } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { injectAction } from '../services/api';

export const VisionControl: FC = () => {
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

  const handleSyncVision = () => {
    injectAction('SYNC_VISION');
  };

  const handleResetZoom = () => {
    injectAction('RESET_ZOOM');
  };

  const handleRotateCW = () => {
    injectAction('ROTATE_CW');
  };

  const handleRotateCCW = () => {
    injectAction('ROTATE_CCW');
  };

  const handleResetView = () => {
    injectAction('RESET_VIEW');
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

      <button
        onClick={handleSyncVision}
        className="w-full bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold py-1.5 px-3 rounded border border-blue-200 transition-colors"
      >
        Sync Vision
      </button>

      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={handleRotateCCW}
          className="bg-gray-50 hover:bg-gray-100 text-gray-700 text-xs font-semibold py-1.5 px-3 rounded border border-gray-200 transition-colors flex items-center justify-center gap-1"
          title="Rotate Counter-Clockwise"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          CCW
        </button>
        <button
          onClick={handleRotateCW}
          className="bg-gray-50 hover:bg-gray-100 text-gray-700 text-xs font-semibold py-1.5 px-3 rounded border border-gray-200 transition-colors flex items-center justify-center gap-1"
          title="Rotate Clockwise"
        >
          CW
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14 5l7 7m0 0l-7 7m7-7H3"
            />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={handleResetZoom}
          className="bg-green-50 hover:bg-green-100 text-green-700 text-xs font-semibold py-1.5 px-3 rounded border border-green-200 transition-colors"
        >
          Zoom 1:1
        </button>
        <button
          onClick={handleResetView}
          className="bg-gray-50 hover:bg-gray-100 text-gray-700 text-xs font-semibold py-1.5 px-3 rounded border border-gray-200 transition-colors"
        >
          Reset All
        </button>
      </div>

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
