from __future__ import annotations
import logging
from typing import Dict, List, Optional, TYPE_CHECKING, Any

from light_map.core.common_types import SceneId
from light_map.visibility.exclusive_vision_scene import ExclusiveVisionScene
from light_map.menu.menu_scene import MenuScene
from light_map.map.map_scene import MapScene, ViewingScene
from light_map.vision.scanning_scene import ScanningScene
from light_map.calibration.calibration_scenes import (
    FlashCalibrationScene,
    MapGridCalibrationScene,
    PpiCalibrationScene,
    IntrinsicsCalibrationScene,
    ProjectorCalibrationScene,
    ExtrinsicsCalibrationScene,
    Projector3DCalibrationScene,
)

if TYPE_CHECKING:
    from light_map.core.scene import Scene, SceneTransition
    from light_map.core.app_context import AppContext
    from light_map.state.world_state import WorldState
    from light_map.core.common_types import Layer


class SceneManager:
    """Manages scene lifecycle, transitions, and layer stacks."""

    def __init__(
        self,
        context: AppContext,
        state: WorldState,
        scene_classes: Optional[Dict[SceneId, type]] = None,
    ):
        self.context = context
        self.state = state
        self.scene_classes = scene_classes
        self.scenes: Dict[SceneId, Scene] = self._initialize_scenes()
        self.current_scene_id: SceneId = SceneId.MENU
        self.current_scene: Scene = self.scenes[self.current_scene_id]

    def _initialize_scenes(self) -> Dict[SceneId, Scene]:
        """Initializes all Scene objects with the shared AppContext."""
        if self.scene_classes:
            return {
                sid: cls(self.context)
                for sid, cls in self.scene_classes.items()
                if sid in SceneId.__members__.values() or sid in self.scene_classes
            }

        return {
            SceneId.MENU: MenuScene(self.context),
            SceneId.VIEWING: ViewingScene(self.context),
            SceneId.MAP: MapScene(self.context),
            SceneId.SCANNING: ScanningScene(self.context),
            SceneId.EXCLUSIVE_VISION: ExclusiveVisionScene(self.context),
            SceneId.CALIBRATE_FLASH: FlashCalibrationScene(self.context),
            SceneId.CALIBRATE_PPI: PpiCalibrationScene(self.context),
            SceneId.CALIBRATE_MAP_GRID: MapGridCalibrationScene(self.context),
            SceneId.CALIBRATE_INTRINSICS: IntrinsicsCalibrationScene(self.context),
            SceneId.CALIBRATE_PROJECTOR: ProjectorCalibrationScene(self.context),
            SceneId.CALIBRATE_EXTRINSICS: ExtrinsicsCalibrationScene(self.context),
            SceneId.CALIBRATE_PROJECTOR_3D: Projector3DCalibrationScene(self.context),
        }

    def transition_to(self, target_id: SceneId, payload: Any = None):
        """
        Handles the exit from the current scene and entry into the target scene.

        Args:
            target_id: The ID of the scene to transition to.
            payload: Optional data to pass to the new scene's on_enter() method.
        """
        if target_id not in self.scenes:
            logging.error("Scene '%s' not found.", target_id)
            return

        logging.debug("Switching scene to: %s", target_id)
        self.current_scene.on_exit()
        self.current_scene_id = target_id
        self.current_scene = self.scenes[target_id]
        self.current_scene.on_enter(payload)

        # Update WorldState to reflect the new active scene name
        self.state._scene_atom.update(self.current_scene.__class__.__name__)

    def handle_transition(self, transition: SceneTransition):
        """Processes a SceneTransition object requested by a scene."""
        self.transition_to(transition.target_scene, transition.payload)

    @property
    def current_scene_name(self) -> str:
        """Returns the string identifier of the current scene."""
        return self.current_scene_id.value

    def get_layer_stack(self) -> List[Layer]:
        """Returns the ordered list of layers for the current scene from the LayerStackManager."""
        if not self.context.layer_manager:
            logging.warning("No layer_manager found in context. Returning empty stack.")
            return []
        return self.context.layer_manager.get_stack(self.current_scene)
