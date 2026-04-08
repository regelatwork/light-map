import React, { useState, useEffect } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { updateSystemConfig } from '../services/api';

export const HardwareAlignment: React.FC = () => {
  const { config } = useSystemState();
  const [localX, setLocalX] = useState<string>('');
  const [localY, setLocalY] = useState<string>('');
  const [localZ, setLocalZ] = useState<string>('');

  // Sync from config when it arrives
  useEffect(() => {
    if (config?.current_projector_pos) {
      setLocalX(config.current_projector_pos[0].toFixed(2));
      setLocalY(config.current_projector_pos[1].toFixed(2));
      setLocalZ(config.current_projector_pos[2].toFixed(2));
    }
  }, [config?.current_projector_pos]);

  const handleUpdate = async (axis: 'x' | 'y' | 'z', value: string) => {
    const numValue = parseFloat(value);
    if (isNaN(numValue)) return;

    try {
      const update: any = {};
      update[`projector_pos_${axis}_override`] = numValue;
      await updateSystemConfig(update);
    } catch (e) {
      console.error(e);
    }
  };

  const handleReset = async () => {
    try {
      await updateSystemConfig({
        projector_pos_x_override: null,
        projector_pos_y_override: null,
        projector_pos_z_override: null,
      });
    } catch (e) {
      console.error(e);
    }
  };

  const calibrated = config?.calibrated_projector_pos;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="font-bold text-gray-800">Projector Position (mm)</h4>
          <button
            onClick={handleReset}
            className="text-xs font-bold text-blue-600 hover:text-blue-800 uppercase tracking-wider"
          >
            Reset to Calibrated
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">
              X (Horizontal)
            </label>
            <input
              type="number"
              step="0.1"
              value={localX}
              onChange={(e) => setLocalX(e.target.value)}
              onBlur={() => handleUpdate('x', localX)}
              className="w-full px-4 py-2 text-sm border-2 border-gray-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium"
            />
            {calibrated && (
              <p className="text-[10px] text-gray-400">Calibrated: {calibrated[0].toFixed(1)}</p>
            )}
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">
              Y (Vertical)
            </label>
            <input
              type="number"
              step="0.1"
              value={localY}
              onChange={(e) => setLocalY(e.target.value)}
              onBlur={() => handleUpdate('y', localY)}
              className="w-full px-4 py-2 text-sm border-2 border-gray-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium"
            />
            {calibrated && (
              <p className="text-[10px] text-gray-400">Calibrated: {calibrated[1].toFixed(1)}</p>
            )}
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">
              Z (Height)
            </label>
            <input
              type="number"
              step="0.1"
              value={localZ}
              onChange={(e) => setLocalZ(e.target.value)}
              onBlur={() => handleUpdate('z', localZ)}
              className="w-full px-4 py-2 text-sm border-2 border-gray-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium"
            />
            {calibrated && (
              <p className="text-[10px] text-gray-400">Calibrated: {calibrated[2].toFixed(1)}</p>
            )}
          </div>
        </div>

        <div className="p-4 bg-blue-50 rounded-xl border border-blue-100 flex gap-3">
          <svg className="w-5 h-5 text-blue-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <p className="text-xs text-blue-700 leading-relaxed">
            Adjust these values to fine-tune the alignment of masks and pointers. 
            Increasing <span className="font-bold">Z</span> will make the projected elements appear smaller and shift towards the projector center (parallax).
          </p>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
          <div>
            <h4 className="font-bold text-gray-800">Use 3D Projective Model</h4>
            <p className="text-sm text-gray-500">Enable advanced 3D math for all visual layers.</p>
          </div>
          <button
            onClick={() => updateSystemConfig({ use_projector_3d_model: !config?.use_projector_3d_model })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none shadow-sm ${
              config?.use_projector_3d_model ? 'bg-blue-600' : 'bg-gray-200'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                config?.use_projector_3d_model ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </section>
    </div>
  );
};
