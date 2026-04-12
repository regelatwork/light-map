import { type FC } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { injectAction, updateSystemConfig } from '../services/api';
import { GlobalConfigNumber, GlobalConfigCheckbox, GlobalConfigSelect } from './common/ConfigInputs';
import { GlobalConfig } from '../types/schema.generated';

interface VisionControlProps {
  showOnlyToggles?: boolean;
}

export const VisionControl: FC<VisionControlProps> = ({ showOnlyToggles = false }) => {
  const { config: rawConfig } = useSystemState();
  const config = rawConfig as unknown as GlobalConfig;

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

  if (!config) return null;

  if (showOnlyToggles) {
    return (
      <div className="space-y-6 text-black">
        <GlobalConfigCheckbox
          name="enable_hand_masking"
          config={config}
          update={updateSystemConfig}
        />

        <GlobalConfigCheckbox
          name="enable_aruco_masking"
          config={config}
          update={updateSystemConfig}
        />

        {config.enable_aruco_masking && (
          <GlobalConfigNumber
            name="aruco_mask_intensity"
            config={config}
            update={updateSystemConfig}
          />
        )}

        <GlobalConfigNumber
          name="pointer_offset_mm"
          config={config}
          update={updateSystemConfig}
        />

        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
          <div>
            <h4 className="font-bold text-gray-800">Fog of War</h4>
            <p className="text-sm text-gray-500">Hides unexplored areas from the players.</p>
          </div>
          <button
            onClick={handleToggleFow}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors shadow-sm ${
              !(config as any).fow_disabled ? 'bg-blue-600' : 'bg-gray-200'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                !(config as any).fow_disabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={handleResetFow}
            className="p-3 bg-white border border-gray-200 rounded-lg text-sm font-semibold hover:bg-orange-50 hover:border-orange-200 hover:text-orange-700 transition-all shadow-sm"
          >
            Reset Fog of War
          </button>
          <button
            onClick={handleSyncVision}
            className="p-3 bg-white border border-gray-200 rounded-lg text-sm font-semibold hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-all shadow-sm"
          >
            Sync Vision
          </button>
        </div>
      </div>
    );
  }

  // Compact Layout for Sidebar/Overlay
  return (
    <div className="space-y-4 text-black">
      <GlobalConfigCheckbox
        name="enable_hand_masking"
        config={config}
        update={updateSystemConfig}
      />

      <GlobalConfigCheckbox
        name="enable_aruco_masking"
        config={config}
        update={updateSystemConfig}
      />

      {config.enable_aruco_masking && (
        <GlobalConfigNumber
          name="aruco_mask_intensity"
          config={config}
          update={updateSystemConfig}
        />
      )}

      <GlobalConfigNumber
        name="pointer_offset_mm"
        config={config}
        update={updateSystemConfig}
      />

      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
        <div>
          <h4 className="font-bold text-gray-800">Fog of War</h4>
          <p className="text-sm text-gray-500">Hides unexplored areas from the players.</p>
        </div>
        <button
          onClick={handleToggleFow}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors shadow-sm ${
            !(config as any).fow_disabled ? 'bg-blue-600' : 'bg-gray-200'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              !(config as any).fow_disabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
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
            (config as any).debug_mode
              ? 'bg-blue-100 text-blue-800 hover:bg-green-200'
              : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
          }`}
        >
          {(config as any).debug_mode ? 'ON' : 'OFF'}
        </button>
      </div>

      <GlobalConfigSelect
        name="gm_position"
        config={config}
        update={updateSystemConfig}
      />
    </div>
  );
};
