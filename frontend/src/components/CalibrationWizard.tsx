import React from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const CalibrationWizard: React.FC = () => {
  const { world } = useSystemState();

  const handleStartCalibration = async (actionId: string) => {
    try {
      await fetch(`/input/action?action=${actionId}`, {
        method: 'POST',
      });
    } catch (e) {
      console.error(`Failed to start calibration: ${actionId}`, e);
    }
  };

  const isCalibrating = world.scene?.startsWith('CALIBRATE_');

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-sm border border-gray-200 p-4 overflow-y-auto">
      <h2 className="mb-4 text-xl font-semibold text-gray-800">Calibration Wizards</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-black rounded-lg overflow-hidden flex items-center justify-center min-h-[300px]">
          <img 
            src="/video_feed" 
            alt="Live Camera Feed" 
            className="w-full h-auto object-contain max-h-[600px]"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              if (e.currentTarget.nextElementSibling) {
                (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'block';
              }
            }}
          />
          <div className="text-gray-500 hidden text-center p-4">
            <p>Video Feed Not Available</p>
            <p className="text-sm">Ensure the Light Map backend is running with a camera.</p>
          </div>
        </div>

        <div className="flex flex-col space-y-3">
          <h3 className="font-semibold text-gray-700 border-b pb-2">Launch Calibration</h3>
          
          <button 
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration('CALIBRATE_INTRINSICS')}
            disabled={isCalibrating}
          >
            1. Camera Intrinsics
          </button>
          
          <button 
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration('CALIBRATE_PROJECTOR')}
            disabled={isCalibrating}
          >
            2. Projector Homography
          </button>
          
          <button 
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration('CALIBRATE_PPI')}
            disabled={isCalibrating}
          >
            3. Physical Scale (PPI)
          </button>
          
          <button 
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration('CALIBRATE_EXTRINSICS')}
            disabled={isCalibrating}
          >
            4. Camera Extrinsics
          </button>

          <button 
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-left mt-4 transition-colors"
            onClick={() => handleStartCalibration('CALIBRATE_FLASH')}
            disabled={isCalibrating}
          >
            Aux: Flash Calibration
          </button>

          <button 
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-left transition-colors"
            onClick={() => handleStartCalibration('SET_MAP_SCALE')}
            disabled={isCalibrating}
          >
            Aux: Map Grid Offset
          </button>
        </div>
      </div>

      <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <h3 className="font-semibold text-gray-800 mb-2">Instructions</h3>
        {world.scene === 'CALIBRATE_INTRINSICS' && (
          <p className="text-gray-600">Hold the checkerboard pattern in front of the camera and move it around. The system will automatically capture frames. When enough frames are captured, it will process and return to the main menu.</p>
        )}
        {world.scene === 'CALIBRATE_PROJECTOR' && (
          <p className="text-gray-600">The projector is displaying a calibration pattern. Ensure the camera can see the projected area clearly. The system will automatically detect the pattern and align the projector.</p>
        )}
        {world.scene === 'CALIBRATE_EXTRINSICS' && (
          <p className="text-gray-600">Place ArUco tokens on the designated target zones shown in the camera view. Once all tokens are valid, use a "Closed Fist" gesture to confirm or wait for automatic validation if applicable.</p>
        )}
        {world.scene === 'CALIBRATE_PPI' && (
          <p className="text-gray-600">Place two tokens next to a ruler or known measurement. The system will detect them. Use gestures to confirm the scale.</p>
        )}
        {world.scene === 'MENU' && (
          <p className="text-gray-600">Select a calibration routine from the list above to begin. The video feed will show you the camera's perspective to assist with placement.</p>
        )}
        {!isCalibrating && world.scene !== 'MENU' && (
          <p className="text-gray-600">Return to the Menu or trigger a calibration routine to begin.</p>
        )}
      </div>
    </div>
  );
};
