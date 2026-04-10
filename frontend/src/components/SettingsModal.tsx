import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCalibration, CalibrationMode } from './CalibrationContext';
import { VisionControl } from './VisionControl';
import { saveGridConfig, injectAction } from '../services/api';
import { HardwareAlignment } from './HardwareAlignment';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'grid' | 'vision' | 'hardware' | 'system';

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { config, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
  const { activeMode, setMode } = useCalibration();
  const isGridEditMode = activeMode === CalibrationMode.GRID;
  const [activeTab, setActiveTab] = useState<Tab>('grid');

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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[90vh] overflow-hidden text-black border border-gray-200">
        {/* Header */}
        <div className="px-6 py-4 border-b flex justify-between items-center bg-gray-50">
          <h2 className="text-xl font-bold text-gray-800">System Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-200"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b px-6 bg-white">
          <button
            onClick={() => setActiveTab('grid')}
            className={`px-4 py-3 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === 'grid'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Grid & Map
          </button>
          <button
            onClick={() => setActiveTab('vision')}
            className={`px-4 py-3 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === 'vision'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Vision & Masking
          </button>
          <button
            onClick={() => setActiveTab('hardware')}
            className={`px-4 py-3 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === 'hardware'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Hardware
          </button>
          <button
            onClick={() => setActiveTab('system')}
            className={`px-4 py-3 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === 'system'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            System & Debug
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8 bg-white">
          {activeTab === 'grid' && (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-200">
              <section className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
                  <div>
                    <h4 className="font-bold text-gray-800">Visual Grid Editor</h4>
                    <p className="text-sm text-gray-500">Enable on-canvas handles for precise grid alignment.</p>
                  </div>
                  <button
                    onClick={() => setMode(isGridEditMode ? CalibrationMode.NONE : CalibrationMode.GRID)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none shadow-sm ${
                      isGridEditMode ? 'bg-blue-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        isGridEditMode ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                {isGridEditMode && (
                  <div className="grid grid-cols-2 gap-6 p-6 bg-blue-50 rounded-xl border border-blue-100 shadow-inner">
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-blue-700 uppercase tracking-wider">Origin X</label>
                      <input
                        type="number"
                        value={Math.round(gridX)}
                        onChange={(e) => setLocalGridX(Number(e.target.value))}
                        onBlur={handleGridSave}
                        className="w-full px-4 py-2 text-sm border-2 border-blue-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-blue-700 uppercase tracking-wider">Origin Y</label>
                      <input
                        type="number"
                        value={Math.round(gridY)}
                        onChange={(e) => setLocalGridY(Number(e.target.value))}
                        onBlur={handleGridSave}
                        className="w-full px-4 py-2 text-sm border-2 border-blue-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium"
                      />
                    </div>
                    <div className="col-span-2 text-xs text-blue-600 bg-blue-100 bg-opacity-50 p-3 rounded-lg flex gap-3">
                      <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                      </svg>
                      <p>Use the <span className="font-bold">Green Handle</span> on canvas to move the origin, or the <span className="font-bold">Blue Handle</span> to adjust scale.</p>
                    </div>
                  </div>
                )}
              </section>

              <section className="space-y-4">
                <h4 className="font-bold text-gray-800 flex items-center gap-2">
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                  </svg>
                  View Controls
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => injectAction('RESET_ZOOM')} className="p-3 bg-white border border-gray-200 rounded-lg text-sm font-semibold hover:bg-gray-50 transition-colors shadow-sm text-gray-700">Zoom 1:1</button>
                  <button onClick={() => injectAction('RESET_VIEW')} className="p-3 bg-white border border-gray-200 rounded-lg text-sm font-semibold hover:bg-gray-50 transition-colors shadow-sm text-gray-700">Reset All</button>
                  <button onClick={() => injectAction('ROTATE_CCW')} className="p-3 bg-white border border-gray-200 rounded-lg text-sm font-semibold hover:bg-gray-50 transition-colors shadow-sm text-gray-700 flex justify-center items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                    Rotate CCW
                  </button>
                  <button onClick={() => injectAction('ROTATE_CW')} className="p-3 bg-white border border-gray-200 rounded-lg text-sm font-semibold hover:bg-gray-50 transition-colors shadow-sm text-gray-700 flex justify-center items-center gap-2">
                    Rotate CW
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                  </button>
                </div>
              </section>
            </div>
          )}

          {activeTab === 'vision' && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-200">
               <VisionControl showOnlyToggles={true} />
            </div>
          )}

          {activeTab === 'hardware' && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-200">
               <HardwareAlignment />
            </div>
          )}

          {activeTab === 'system' && (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-200">
              <section className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
                  <div>
                    <h4 className="font-bold text-gray-800">Debug Overlay</h4>
                    <p className="text-sm text-gray-500">Show FPS, scene name, and hand tracking raw data on projection.</p>
                  </div>
                  <button
                    onClick={() => injectAction('TOGGLE_DEBUG_MODE')}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors shadow-sm ${
                      config?.debug_mode ? 'bg-blue-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        config?.debug_mode ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </section>

              <section className="space-y-4">
                <label className="block text-sm font-bold text-gray-700 uppercase tracking-wider">GM Position</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    'None', 'North', 'South', 'East', 'West',
                    'North West', 'North East', 'South West', 'South East'
                  ].map((pos) => (
                    <button
                      key={pos}
                      onClick={() => injectAction('SET_GM_POSITION', pos)}
                      className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-all ${
                        config?.gm_position === pos
                          ? 'bg-blue-600 text-white border-blue-600 shadow-md transform scale-105'
                          : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                      }`}
                    >
                      {pos}
                    </button>
                  ))}
                </div>
              </section>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-blue-600 text-white font-bold rounded-lg hover:bg-blue-700 transition-all shadow-md active:scale-95"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
