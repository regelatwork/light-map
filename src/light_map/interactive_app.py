import cv2
import numpy as np
import time
from typing import List, Tuple, Any, Optional, Dict
from dataclasses import dataclass
import mediapipe as mp

from light_map.common_types import GestureType, MenuItem, AppMode, MenuActions
from light_map.input_manager import InputManager
from light_map.menu_system import MenuSystem
from light_map.renderer import Renderer
from light_map.gestures import detect_gesture
from light_map.map_system import MapSystem
from light_map.svg_loader import SVGLoader
import light_map.menu_config as config_vars
from light_map.map_config import MapConfigManager
from light_map.calibration_logic import calculate_ppi_from_frame


@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    root_menu: MenuItem


class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        self.config = config
        self.time_provider = time_provider

        self.menu_system = MenuSystem(
            config.width, config.height, config.root_menu, time_provider=time_provider
        )
        self.renderer = Renderer(config.width, config.height)
        self.input_manager = InputManager(time_provider=time_provider)

        # Map Support
        self.map_system = MapSystem(config.width, config.height)
        self.svg_loader: Optional[SVGLoader] = None
        self.map_config = MapConfigManager()  # Load config

        # Load global PPI
        # TODO: Pass PPI to somewhere? MapSystem doesn't need it for rendering,
        # but SVGLoader might if we want real-scale by default.
        # Currently SVGLoader assumes 1 unit = 1 px.
        # Real Scale: Scale Factor = PPI / 96.0
        # We should store this.

        # State
        self.mode = AppMode.MENU
        self.last_fps_time = 0.0
        self.fps = 0.0
        self.debug_mode = False

        # Latest Menu State for rendering
        self.menu_state = self.menu_system.update(-1, -1, GestureType.NONE)

        # Interaction State
        self.last_cursor_pos = None  # (x, y) for panning
        self.zoom_start_dist = None  # distance between hands when zoom started
        self.zoom_start_level = 1.0
        self.zoom_gesture_start_time = 0.0

        # Calibration State
        self.calib_stage = 0  # 0: Capture, 1: Confirm
        self.calib_candidate_ppi = 0.0

    def set_debug_mode(self, enabled: bool):
        self.debug_mode = enabled

    def load_map(self, filename: str):
        """Loads an SVG map file and restores viewport."""
        self.svg_loader = SVGLoader(filename)

        # Restore viewport
        vp = self.map_config.get_map_viewport(filename)
        self.map_system.set_state(vp.x, vp.y, vp.zoom, vp.rotation)

        # Save current map filename if needed, though config manager handles saving on change
        # self.map_config.data.global_settings.last_used_map = filename
        # self.map_config.save()

    def save_current_map_state(self):
        if self.svg_loader:
            s = self.map_system.state
            self.map_config.save_map_viewport(
                self.svg_loader.filename, s.x, s.y, s.zoom, s.rotation
            )

    def reload_config(self, config: AppConfig):
        """Reloads the application configuration and re-initializes necessary components."""
        self.config = config
        self.menu_system = MenuSystem(
            config.width,
            config.height,
            config.root_menu,
            time_provider=self.time_provider,
        )
        self.renderer = Renderer(config.width, config.height)
        self.map_system = MapSystem(config.width, config.height)
        self.menu_state = self.menu_system.update(-1, -1, GestureType.NONE)

    def process_frame(
        self, frame: np.ndarray, results: Any
    ) -> Tuple[np.ndarray, List[str]]:
        current_time = self.time_provider()

        # 1. Update FPS
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        # 2. Extract Hand Data
        hands_data = self._extract_hands(results, frame.shape)
        hand_count = len(hands_data)

        # 3. Mode-Specific Processing
        actions = []
        if self.mode == AppMode.MENU:
            actions = self._process_menu_mode(hands_data)
        elif self.mode == AppMode.MAP:
            actions = self._process_map_mode(hands_data, current_time)
        elif self.mode == AppMode.CALIB_PPI:
            actions = self._process_calib_ppi_mode(hands_data, frame)

        # 4. Render Layers
        # A. Map Background
        map_image = None
        if self.svg_loader:
            params = self.map_system.get_render_params()
            map_image = self.svg_loader.render(
                self.config.width, self.config.height, **params
            )

        # B. Menu/Overlay
        # Render menu only if NOT in calibration mode (or maybe background?)
        # If Calibrating, we might want to hide menu.
        if self.mode == AppMode.CALIB_PPI:
            output = np.zeros(
                (self.config.height, self.config.width, 3), dtype=np.uint8
            )
            # Calibration Overlay is drawn in _draw_calib_overlay
        else:
            output = self.renderer.render(self.menu_state, background=map_image)

        # C. Overlays
        if self.mode == AppMode.MAP:
            self._draw_map_overlay(output)
        elif self.mode == AppMode.CALIB_PPI:
            self._draw_calib_overlay(output)

        # D. Debug Overlays
        if self.debug_mode:
            primary_gesture = GestureType.NONE
            px, py = -1, -1
            if hands_data:
                primary_gesture = hands_data[0]["gesture"]
                px, py = hands_data[0]["proj_pos"]
            self._draw_debug_overlay(output, hand_count, primary_gesture, px, py)

        return output, actions

    def _extract_hands(self, results, frame_shape) -> List[Dict]:
        """Extracts and transforms hand data from MediaPipe results."""
        hands_data = []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return hands_data

        matrix = self.config.projector_matrix.astype(np.float32)

        for i in range(len(results.multi_hand_landmarks)):
            landmarks = results.multi_hand_landmarks[i]
            handedness = results.multi_handedness[i]
            label = handedness.classification[0].label

            gesture = detect_gesture(landmarks.landmark, label)

            # Projector Position (Index Tip)
            tip = landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
            cx = int(tip.x * frame_shape[1])
            cy = int(tip.y * frame_shape[0])

            camera_point = np.array([cx, cy], dtype=np.float32).reshape(1, 1, 2)
            projector_point = cv2.perspectiveTransform(camera_point, matrix)
            px, py = int(projector_point[0][0][0]), int(projector_point[0][0][1])

            hands_data.append(
                {"gesture": gesture, "proj_pos": (px, py), "raw_landmarks": landmarks}
            )

        return hands_data

    def _process_menu_mode(self, hands_data: List[Dict]) -> List[str]:
        px, py = -1, -1
        gesture = GestureType.NONE
        is_present = False

        if hands_data:
            px, py = hands_data[0]["proj_pos"]
            gesture = hands_data[0]["gesture"]
            is_present = True

        self.input_manager.update(px, py, gesture, is_present)

        self.menu_state = self.menu_system.update(
            self.input_manager.get_x(),
            self.input_manager.get_y(),
            self.input_manager.get_gesture(),
        )

        actions = []
        if self.menu_state.just_triggered_action:
            action = self.menu_state.just_triggered_action
            if action == MenuActions.MAP_CONTROLS:
                self.mode = AppMode.MAP
            elif action == MenuActions.CALIBRATE_SCALE:
                self.mode = AppMode.CALIB_PPI
                self.calib_stage = 0  # Capture
            elif action == MenuActions.ROTATE_CW:
                self.map_system.rotate(90)
                self.save_current_map_state()
            elif action == MenuActions.ROTATE_CCW:
                self.map_system.rotate(-90)
                self.save_current_map_state()
            elif action == MenuActions.RESET_VIEW:
                self.map_system.reset_view()
                self.save_current_map_state()
            else:
                actions.append(action)

        return actions

    def _process_map_mode(
        self, hands_data: List[Dict], current_time: float
    ) -> List[str]:
        # 1. Zoom
        pointing_hands = [h for h in hands_data if h["gesture"] == GestureType.POINTING]
        if len(pointing_hands) >= 2:
            p1 = np.array(pointing_hands[0]["proj_pos"])
            p2 = np.array(pointing_hands[1]["proj_pos"])
            dist = np.linalg.norm(p1 - p2)

            if self.zoom_gesture_start_time == 0:
                self.zoom_gesture_start_time = current_time
            elif current_time - self.zoom_gesture_start_time > config_vars.ZOOM_DELAY:
                if self.zoom_start_dist is None:
                    self.zoom_start_dist = dist
                    self.zoom_start_level = self.map_system.state.zoom
                else:
                    factor = dist / self.zoom_start_dist
                    new_zoom = self.zoom_start_level * factor
                    center = (p1 + p2) / 2
                    delta_factor = new_zoom / self.map_system.state.zoom
                    self.map_system.zoom(delta_factor, center[0], center[1])
        else:
            self.zoom_gesture_start_time = 0
            self.zoom_start_dist = None

        # 2. Pan
        if self.zoom_start_dist is None:
            if hands_data and hands_data[0]["gesture"] == config_vars.PAN_GESTURE:
                pos = hands_data[0]["proj_pos"]
                if self.last_cursor_pos is not None:
                    dx = pos[0] - self.last_cursor_pos[0]
                    dy = pos[1] - self.last_cursor_pos[1]
                    self.map_system.pan(dx, dy)
                self.last_cursor_pos = pos
            else:
                self.last_cursor_pos = None

        # Save state on interaction end?
        # Too frequent. Ideally on exit or periodic.
        # Let's save on Exit.

        # Exit
        if hands_data and hands_data[0]["gesture"] == config_vars.SUMMON_GESTURE:
            self.save_current_map_state()
            self.mode = AppMode.MENU

        return []

    def _process_calib_ppi_mode(
        self, hands_data: List[Dict], frame: np.ndarray
    ) -> List[str]:
        # Stage 0: Capture & Detect
        if self.calib_stage == 0:
            # We try to detect markers every frame (or could wait for stability)
            # Pass frame (BGR) and projector matrix
            ppi = calculate_ppi_from_frame(frame, self.config.projector_matrix)
            if ppi:
                self.calib_candidate_ppi = ppi
                self.calib_stage = 1  # Confirm

        # Stage 1: Confirm (Grid is shown in draw)
        elif self.calib_stage == 1:
            # Check for gestures
            if hands_data:
                gesture = hands_data[0]["gesture"]
                # Confirm: Thumb Up (Victory/Gun/Thumb?)
                # menu_config defines SUMMON_GESTURE=VICTORY
                # Let's use VICTORY for confirm as well for consistency?
                # Or Thumb Up if we had it. We have 'Gun' which uses thumb.
                # Let's use VICTORY ("Peace/Confirm")

                if gesture == GestureType.VICTORY:
                    # Save
                    self.map_config.set_ppi(self.calib_candidate_ppi)
                    self.mode = AppMode.MENU
                elif gesture == GestureType.OPEN_PALM:
                    # Retry
                    self.calib_stage = 0

        return []

    def _draw_calib_overlay(self, image):
        if self.calib_stage == 0:
            cv2.putText(
                image,
                "Place Calibration Target",
                (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                image,
                "Searching for markers...",
                (50, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
        elif self.calib_stage == 1:
            # Draw Grid based on candidate PPI
            ppi = self.calib_candidate_ppi
            if ppi > 0:
                step = int(ppi)  # 1 inch
                h, w = image.shape[:2]
                # Draw vertical lines
                for x in range(0, w, step):
                    cv2.line(image, (x, 0), (x, h), (0, 50, 0), 1)
                # Draw horizontal lines
                for y in range(0, h, step):
                    cv2.line(image, (0, y), (w, y), (0, 50, 0), 1)

            cv2.putText(
                image,
                f"PPI Detected: {ppi:.2f}",
                (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                image,
                "Confirm: VICTORY | Retry: OPEN PALM",
                (50, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

    def _draw_map_overlay(self, image):
        # Instructions
        cv2.putText(
            image,
            "MAP MODE | Panning: Fist | Zoom: Two-Hand Pointing | Exit: Victory",
            (50, self.config.height - 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )
        # Zoom level
        zoom_pct = int(self.map_system.state.zoom * 100)
        cv2.putText(
            image,
            f"Zoom: {zoom_pct}%",
            (50, self.config.height - 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

    def _draw_debug_overlay(self, image, hand_count, gesture, x, y):
        cv2.putText(
            image,
            f"FPS: {int(self.fps)} | Mode: {self.mode}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            image,
            f"Hands: {hand_count}",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        if gesture != GestureType.NONE:
            dx = max(0, min(x, self.config.width))
            dy = max(0, min(y, self.config.height))
            label = gesture.name if isinstance(gesture, GestureType) else str(gesture)
            cv2.putText(
                image,
                label,
                (dx, dy - 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )
            cv2.circle(image, (dx, dy), 10, (0, 255, 255), -1)
