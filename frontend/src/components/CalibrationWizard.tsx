import React from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { SceneId, MenuActions } from '../types/system';

export const CalibrationWizard: React.FC = () => {
  const { world, config } = useSystemState();

  const handleStartCalibration = async (actionId: MenuActions) => {
    try {
      await fetch(`/input/action?action=${actionId}`, {
        method: 'POST',
      });
    } catch (e) {
      console.error(`Failed to start calibration: ${actionId}`, e);
    }
  };

  const isCalibrating = typeof world.scene === 'string' && world.scene.startsWith('CALIBRATE_');

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-sm border border-gray-200 p-4 overflow-y-auto">
      <h2 className="mb-4 text-xl font-semibold text-gray-800">Calibration Wizards</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-black rounded-lg overflow-hidden flex items-center justify-center min-h-[300px]">
          {world.scene === SceneId.CALIBRATE_STEREO ? (
            <div className="grid grid-cols-2 gap-2 w-full h-full p-2">
              <div className="relative">
                <span className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                  Camera Left
                </span>
                <img
                  src="/video_feed?camera=left"
                  alt="Camera Left Feed"
                  className="w-full h-auto object-contain max-h-[600px]"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).src = '/video_feed';
                  }}
                />
              </div>
              <div className="relative">
                <span className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                  Camera Right
                </span>
                <img
                  src="/video_feed?camera=right"
                  alt="Camera Right Feed"
                  className="w-full h-auto object-contain max-h-[600px]"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).src = '/video_feed';
                  }}
                />
              </div>
            </div>
          ) : (
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
          )}
          <div className="text-gray-500 hidden text-center p-4">
            <p>Video Feed Not Available</p>
            <p className="text-sm">Ensure the Light Map backend is running with a camera.</p>
          </div>
        </div>

        <div className="flex flex-col space-y-3">
          <h3 className="font-semibold text-gray-700 border-b pb-2">Launch Calibration</h3>

          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_INTRINSICS)}
            disabled={isCalibrating}
          >
            1. Camera Intrinsics
          </button>

          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_PROJECTOR)}
            disabled={isCalibrating}
          >
            2. Projector Homography
          </button>

          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_PPI)}
            disabled={isCalibrating}
          >
            3. Physical Scale (PPI)
          </button>

          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_EXTRINSICS)}
            disabled={isCalibrating}
          >
            4. Camera Extrinsics
          </button>

          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_PROJECTOR_3D)}
            disabled={isCalibrating}
          >
            5. Projector 3D Pose
          </button>

          <button
            className={`px-4 py-2 text-white rounded text-left transition-colors ${
              !config.stereo_vision?.enable_stereo
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_STEREO)}
            disabled={isCalibrating || !config.stereo_vision?.enable_stereo}
            title={
              !config.stereo_vision?.enable_stereo
                ? 'Enable Stereo Vision in Settings to calibrate dual cameras'
                : 'Launch single-sweep stereo calibration'
            }
          >
            6. Stereo Vision Calibration
          </button>

          <button
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-left mt-4 transition-colors"
            onClick={() => handleStartCalibration(MenuActions.CALIBRATE_FLASH)}
            disabled={isCalibrating}
          >
            Aux: Flash Calibration
          </button>
        </div>
      </div>

      <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <h3 className="font-semibold text-gray-800 mb-2">Instructions</h3>
        {world.scene === SceneId.CALIBRATE_INTRINSICS && (
          <p className="text-gray-600">
            Hold the checkerboard pattern in front of the camera and move it around. The system will
            automatically capture frames. When enough frames are captured, it will process and
            return to the main menu.
          </p>
        )}
        {world.scene === SceneId.CALIBRATE_PROJECTOR && (
          <p className="text-gray-600">
            The projector is displaying a calibration pattern. Ensure the camera can see the
            projected area clearly. The system will automatically detect the pattern and align the
            projector.
          </p>
        )}
        {world.scene === SceneId.CALIBRATE_EXTRINSICS && (
          <p className="text-gray-600">
            Place ArUco tokens on the designated target zones shown in the camera view. Once all
            tokens are valid, use a "Closed Fist" gesture to confirm or wait for automatic
            validation if applicable.
          </p>
        )}
        {world.scene === SceneId.CALIBRATE_PPI && (
          <p className="text-gray-600">
            Place two tokens next to a ruler or known measurement. The system will detect them. Use
            gestures to confirm the scale.
          </p>
        )}
        {world.scene === SceneId.CALIBRATE_PROJECTOR_3D && (
          <p className="text-gray-600">
            Place the 3D calibration target at the indicated tabletop positions. The system will capture
            points to compute projector extrinsics.
          </p>
        )}
        {world.scene === SceneId.CALIBRATE_STEREO && (
          <div className="space-y-2 text-gray-600">
            <p className="font-medium text-gray-800">Single-Sweep Stereo Calibration Active:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                Place 4 elevated PC tokens (IDs 0–3: Cricket, Lace, Shikra, Verita) on the illuminated
                corner target rings.
              </li>
              <li>
                Place the physical PPI sheet (IDs 40 & 41) flat on the table within both camera views.
              </li>
              <li>
                Ensure projected grid markers (IDs 42–49) are unobstructed on the table surface.
              </li>
            </ul>
            <p className="text-sm text-gray-500">
              The system will solve relative camera translation (+Tx), rotation, table homography, and
              digital sensor crops in a single pass.
            </p>
          </div>
        )}
        {world.scene === SceneId.MENU && (
          <p className="text-gray-600">
            Select a calibration routine from the list above to begin. The video feed will show you
            the camera's perspective to assist with placement.
          </p>
        )}
        {!isCalibrating && world.scene !== SceneId.MENU && (
          <p className="text-gray-600">
            Return to the Menu or trigger a calibration routine to begin.
          </p>
        )}
      </div>
    </div>
  );
};
