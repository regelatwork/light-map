import cv2
import numpy as np
import time
import copy
from typing import List, Tuple, Any, Optional, Dict
from dataclasses import dataclass, field
import mediapipe as mp

from light_map.common_types import GestureType, MenuItem, AppMode, MenuActions, Token, SessionData, ViewportState
from light_map.input_manager import InputManager
from light_map.menu_system import MenuSystem
from light_map.renderer import Renderer
from light_map.gestures import detect_gesture
from light_map.map_system import MapSystem
from light_map.svg_loader import SVGLoader
import light_map.menu_config as config_vars
from light_map.map_config import MapConfigManager
from light_map.calibration_logic import calculate_ppi_from_frame
from light_map.session_manager import SessionManager
from light_map.token_tracker import TokenTracker
from light_map.menu_builder import build_root_menu


@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    root_menu: MenuItem
    map_search_patterns: List[str] = field(default_factory=list)


class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        self.config = config
        self.time_provider = time_provider

        # Map Support (Init first to build menu)
        self.map_system = MapSystem(config.width, config.height)
        self.svg_loader: Optional[SVGLoader] = None
        self.map_config = MapConfigManager()  # Load config

        # Scan for maps if provided
        if config.map_search_patterns:
             self.map_config.scan_for_maps(config.map_search_patterns)

        # Build dynamic root menu
        dynamic_root = build_root_menu(self.map_config)

        self.menu_system = MenuSystem(
            config.width, config.height, dynamic_root, time_provider=time_provider
        )
        self.renderer = Renderer(config.width, config.height)
        self.input_manager = InputManager(time_provider=time_provider)

        # Token Tracking Support
        self.token_tracker = TokenTracker()
        self.ghost_tokens: List[Token] = []
        self.scan_start_time = 0.0
        self.scan_stage = 0 # 0: White, 1: Capture, 2: Process, 3: Done
        self.last_scan_result_count = 0

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
        self.zoom_start_world_center = None
        self.zoom_gesture_start_time = 0.0
        self.summon_gesture_start_time = 0.0
        self.is_interacting = False  # Track if user is manipulating map
        self.mode_transition_start_time = 0.0

        # Calibration State
        self.calib_stage = 0  # 0: Capture, 1: Confirm
        self.calib_candidate_ppi = 0.0
        self.calib_map_grid_size_inches = 1.0  # Default grid reference size
        
        self.saved_map_state = None
        self.current_base_scale = 1.0

    def set_debug_mode(self, enabled: bool):
        self.debug_mode = enabled

    def load_map(self, filename: str):
        """Loads an SVG map file and restores viewport."""
        self.svg_loader = SVGLoader(filename)

        # Grid Detection & Auto-Config
        entry = self.map_config.data.maps.get(filename)
        
        # If grid spacing is unknown (0.0), try to detect it
        if not entry or entry.grid_spacing_svg <= 0:
            spacing = self.svg_loader.detect_grid_spacing()
            if spacing > 0:
                print(f"Auto-detected grid spacing for {filename}: {spacing} SVG units")
                
                # Calculate initial 1:1 scale assumption (1 grid unit = 1 inch)
                ppi = self.map_config.get_ppi()
                physical_unit = 1.0
                scale_1to1 = (ppi * physical_unit) / spacing
                
                self.map_config.save_map_grid_config(
                    filename,
                    grid_spacing_svg=spacing,
                    grid_origin_svg_x=0.0,
                    grid_origin_svg_y=0.0,
                    physical_unit_inches=physical_unit,
                    scale_factor_1to1=scale_1to1,
                )
        else:
            print(f"Grid spacing for {filename} loaded from config: {entry.grid_spacing_svg} SVG units")

        # Restore viewport
        vp = self.map_config.get_map_viewport(filename)
        self.map_system.set_state(vp.x, vp.y, vp.zoom, vp.rotation)
        
        # Set base scale
        if entry and entry.scale_factor_1to1 > 0:
            self.current_base_scale = entry.scale_factor_1to1
        else:
            self.current_base_scale = 1.0

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
        
        dynamic_root = build_root_menu(self.map_config)
        
        self.menu_system = MenuSystem(
            config.width,
            config.height,
            dynamic_root,
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
        elif self.mode == AppMode.SCANNING:
            self._process_scanning_mode(frame, current_time)
        elif self.mode == AppMode.CALIB_PPI:
            actions = self._process_calib_ppi_mode(hands_data, frame)
        elif self.mode == AppMode.CALIB_MAP_GRID:
            actions = self._process_calib_map_grid_mode(hands_data, current_time)

        # 4. Render Layers
        # A. Map Background
        map_image = None
        if self.svg_loader:
            params = self.map_system.get_render_params()
            quality = 0.25 if self.is_interacting else 1.0
            map_image = self.svg_loader.render(
                self.config.width, self.config.height, quality=quality, **params
            )

        # B. Menu/Overlay
        # SCANNING MODE OVERRIDE
        if self.mode == AppMode.SCANNING:
            if self.scan_stage < 2:
                # White Flash
                output = np.full((self.config.height, self.config.width, 3), 255, dtype=np.uint8)
                # Add "Scanning..." text just in case user is confused (will be projected)
                # Ideally pure white for detection, but small text in corner is fine if masked.
                # But TokenTracker masking logic is not dynamic here.
                # Let's keep it pure white.
            else:
                # Result Stage (Background can be Map or Black)
                # Let's show Map to see ghost tokens overlay immediately
                if map_image is not None:
                    output = map_image.copy()
                else:
                    output = np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)
                
                self._draw_ghost_tokens(output)
                cv2.putText(output, f"Saved {self.last_scan_result_count} Tokens", 
                           (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

        elif self.mode == AppMode.CALIB_PPI:
            output = np.zeros(
                (self.config.height, self.config.width, 3), dtype=np.uint8
            )
        elif self.mode == AppMode.CALIB_MAP_GRID:
            # Show map dimmed so grid is visible
            if map_image is not None:
                output = cv2.convertScaleAbs(map_image, alpha=0.5, beta=0)
            else:
                output = np.zeros(
                    (self.config.height, self.config.width, 3), dtype=np.uint8
                )
        else:
            # Determine Map Opacity based on mode
            map_opacity = 1.0
            if self.menu_state.is_visible:
                # Menu Isolation: Hide map completely when menu is open
                map_opacity = 0.0
            elif self.mode == AppMode.MAP:
                # Interactive Dimming: Dim map slightly to reduce glare
                map_opacity = 0.5

            output = self.renderer.render(
                self.menu_state, background=map_image, map_opacity=map_opacity
            )
            
            # Draw Ghost Tokens in MAP mode (if any)
            if self.mode == AppMode.MAP and self.ghost_tokens:
                self._draw_ghost_tokens(output)

        # C. Overlays
        if self.mode == AppMode.MAP:
            self._draw_map_overlay(output)
        elif self.mode == AppMode.CALIB_PPI:
            self._draw_calib_overlay(output)
        elif self.mode == AppMode.CALIB_MAP_GRID:
            self._draw_calib_map_grid_overlay(output)

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
            action_raw = self.menu_state.just_triggered_action
            
            # Parse pipe for payload
            if "|" in action_raw:
                parts = action_raw.split("|", 1)
                action = parts[0]
                payload = parts[1]
            else:
                action = action_raw
                payload = None
            
            current_time = self.time_provider()
            
            if action == MenuActions.MAP_CONTROLS:
                self.mode = AppMode.MAP
                self.mode_transition_start_time = current_time
            elif action == "LOAD_MAP":
                if payload:
                    self.load_map(payload)
                    self.mode = AppMode.MAP
                    self.mode_transition_start_time = current_time
            elif action == "LOAD_SESSION":
                if payload:
                    session = SessionManager.load_for_map(payload)
                    if session:
                        print(f"Loaded session with {len(session.tokens)} tokens.")
                        if session.map_file:
                             self.load_map(session.map_file)
                        if session.viewport:
                             self.map_system.set_state(
                                 session.viewport.x, session.viewport.y, 
                                 session.viewport.zoom, session.viewport.rotation
                             )
                        self.ghost_tokens = session.tokens
                        self.mode = AppMode.MAP
                        self.mode_transition_start_time = current_time
            elif action == "CALIBRATE_MAP":
                if payload:
                    self.load_map(payload)
                    self.mode = AppMode.CALIB_MAP_GRID
                    self.mode_transition_start_time = current_time
                    self.calib_map_grid_size_inches = 1.0 
                    self.saved_map_state = copy.deepcopy(self.map_system.state)
                    self.map_system.state.rotation = 0.0
                    self.map_system.state.x = 0.0
                    self.map_system.state.y = 0.0
                    self.map_system.state.zoom = self.current_base_scale
            elif action == "FORGET_MAP":
                 if payload:
                     self.map_config.forget_map(payload)
                     new_root = build_root_menu(self.map_config)
                     self.menu_system.set_root_menu(new_root)
            elif action == "SCAN_FOR_MAPS":
                 if self.config.map_search_patterns:
                     self.map_config.scan_for_maps(self.config.map_search_patterns)
                     new_root = build_root_menu(self.map_config)
                     self.menu_system.set_root_menu(new_root)
                     
            elif action == MenuActions.CALIBRATE_SCALE:
                self.mode = AppMode.CALIB_PPI
                self.mode_transition_start_time = current_time
                self.calib_stage = 0  # Capture
            elif action == MenuActions.SET_MAP_SCALE:
                self.mode = AppMode.CALIB_MAP_GRID
                self.mode_transition_start_time = current_time
                # Default to 1 inch for now. Could implement sub-menu for 6in, 1ft, 1m later.
                self.calib_map_grid_size_inches = 1.0 
                
                # Save current user view
                self.saved_map_state = copy.deepcopy(self.map_system.state)
                
                # Reset Map View for Calibration (Base View)
                self.map_system.state.rotation = 0.0
                self.map_system.state.x = 0.0
                self.map_system.state.y = 0.0
                
                # Set initial zoom to current base scale
                self.map_system.state.zoom = self.current_base_scale
            elif action == MenuActions.RESET_ZOOM:
                # Reset zoom to 1:1 (User Zoom = 1, so Total Zoom = Base Scale)
                self.map_system.state.zoom = self.current_base_scale
            elif action == MenuActions.ROTATE_CW:
                self.map_system.rotate(90)
                self.save_current_map_state()
            elif action == MenuActions.ROTATE_CCW:
                self.map_system.rotate(-90)
                self.save_current_map_state()
            elif action == MenuActions.RESET_VIEW:
                self.map_system.reset_view()
                self.map_system.state.zoom = self.current_base_scale
                self.save_current_map_state()
            elif action == MenuActions.SCAN_SESSION:
                if self.svg_loader:
                     self.mode = AppMode.SCANNING
                     self.mode_transition_start_time = current_time
                     self.scan_start_time = current_time
                     self.scan_stage = 0
                     self.last_scan_result_count = 0
                else:
                     print("Cannot scan without a loaded map.")
            elif action == MenuActions.LOAD_SESSION:
                 # Legacy "Load Session" for last active map?
                 # Or session.json?
                 # Keep existing behavior for "session.json"
                 session = SessionManager.load_session("session.json")
                 if session:
                     print(f"Loaded session with {len(session.tokens)} tokens.")
                     # Restore Map & Viewport
                     if session.map_file:
                         self.load_map(session.map_file)
                     
                     if session.viewport:
                         self.map_system.set_state(
                             session.viewport.x, session.viewport.y, 
                             session.viewport.zoom, session.viewport.rotation
                         )
                         
                     self.ghost_tokens = session.tokens
                     self.mode = AppMode.MAP # Go to map to see tokens
                     self.mode_transition_start_time = current_time
                 else:
                     print("Failed to load session.")
            else:
                actions.append(action)

        return actions

    def _process_map_mode(
        self, hands_data: List[Dict], current_time: float
    ) -> List[str]:
        self.is_interacting = False
        
        # Mode Transition Delay
        if current_time - self.mode_transition_start_time < config_vars.MODE_TRANSITION_DELAY:
            return []

        # 1. Zoom
        pointing_hands = [h for h in hands_data if h["gesture"] == GestureType.POINTING]
        if len(pointing_hands) >= 2:
            self.is_interacting = True
            p1 = np.array(pointing_hands[0]["proj_pos"])
            p2 = np.array(pointing_hands[1]["proj_pos"])
            dist = np.linalg.norm(p1 - p2)

            if self.zoom_gesture_start_time == 0:
                self.zoom_gesture_start_time = current_time
            elif current_time - self.zoom_gesture_start_time > config_vars.ZOOM_DELAY:
                # Calculate screen center (Fixed Pivot)
                screen_cx = self.config.width / 2
                screen_cy = self.config.height / 2
                
                if self.zoom_start_dist is None:
                    # Start of gesture
                    self.zoom_start_dist = dist
                    self.zoom_start_level = self.map_system.state.zoom
                    # Calculate world coordinate under the screen center
                    wx, wy = self.map_system.screen_to_world(screen_cx, screen_cy)
                    self.zoom_start_world_center = (wx, wy)
                else:
                    # Update zoom
                    factor = dist / self.zoom_start_dist
                    new_zoom = self.zoom_start_level * factor
                    
                    # Apply new zoom using robust pivot logic
                    wx, wy = self.zoom_start_world_center
                    self.map_system.set_zoom_around_pivot(new_zoom, screen_cx, screen_cy, wx, wy)
        else:
            self.zoom_gesture_start_time = 0
            self.zoom_start_dist = None
            self.zoom_start_world_center = None

        # 2. Pan
        if self.zoom_start_dist is None:
            if hands_data and hands_data[0]["gesture"] == config_vars.PAN_GESTURE:
                self.is_interacting = True
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
            if self.summon_gesture_start_time == 0:
                self.summon_gesture_start_time = current_time
            elif (
                current_time - self.summon_gesture_start_time > config_vars.SUMMON_TIME
            ):
                self.save_current_map_state()
                self.mode = AppMode.MENU
                self.summon_gesture_start_time = 0
        else:
            self.summon_gesture_start_time = 0

        return []

    def _process_scanning_mode(self, frame: np.ndarray, current_time: float):
        # State machine
        # 0: White Flash (Wait for settling)
        # 1: Capture & Process (One shot)
        # 2: Done (Show feedback)
        
        if self.scan_stage == 0:
            if current_time - self.scan_start_time > 0.5: # 500ms settle time
                self.scan_stage = 1
        
        elif self.scan_stage == 1:
            # Detect
            print("Scanning...")
            
            # Use masked ROI for UI if needed (top strip 150px)
            # Assuming standard layout where UI might be projected.
            # But in Flash Mode, we project WHITE. So no UI to mask!
            # Unless debug overlay is burnt in? No.
            # So pass empty mask_rois unless we have known blind spots.
            
            grid_spacing = 0.0
            if self.svg_loader:
                entry = self.map_config.data.maps.get(self.svg_loader.filename)
                if entry:
                    grid_spacing = entry.grid_spacing_svg
            
            ppi = self.map_config.get_ppi()
                
            tokens = self.token_tracker.detect_tokens(
                frame_white=frame,
                projector_matrix=self.config.projector_matrix,
                map_system=self.map_system,
                grid_spacing_svg=grid_spacing,
                ppi=ppi
            )
            
            self.last_scan_result_count = len(tokens)
            self.ghost_tokens = tokens
            print(f"Detected {len(tokens)} tokens.")
            
            # Save Session
            map_file = self.svg_loader.filename if self.svg_loader else ""
            session = SessionData(
                map_file=map_file,
                viewport=ViewportState(
                    self.map_system.state.x,
                    self.map_system.state.y,
                    self.map_system.state.zoom,
                    self.map_system.state.rotation
                ),
                tokens=tokens
            )
            SessionManager.save_session("session.json", session)
            
            self.scan_stage = 2
            self.scan_start_time = current_time # Reuse for display timer

        elif self.scan_stage == 2:
            if current_time - self.scan_start_time > 2.0: # Show result for 2s
                self.mode = AppMode.MAP

    def _draw_ghost_tokens(self, image: np.ndarray):
        if not self.ghost_tokens:
            return
            
        ppi = self.map_config.get_ppi()
        radius = int(ppi * 0.5) if ppi > 0 else 20
        
        for t in self.ghost_tokens:
            # Transform World -> Screen
            sx, sy = self.map_system.world_to_screen(t.world_x, t.world_y)
            
            # Check if within screen
            if 0 <= sx < self.config.width and 0 <= sy < self.config.height:
                # Draw "Ghost" Circle (e.g. Cyan outline)
                cv2.circle(image, (int(sx), int(sy)), radius, (255, 255, 0), 2)
                # Draw ID?
                # cv2.putText(image, str(t.id), (int(sx), int(sy)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

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

    def _process_calib_map_grid_mode(
        self, hands_data: List[Dict], current_time: float
    ) -> List[str]:
        # Reuse map interaction logic for Pan/Zoom
        # We can refactor _process_map_mode to be reusable or just call it?
        # But _process_map_mode handles Exit logic differently.
        # Let's copy-paste relevant parts for now or refactor later.
        
        self.is_interacting = False
        
        # Mode Transition Delay
        if current_time - self.mode_transition_start_time < config_vars.MODE_TRANSITION_DELAY:
            return []
        
        # 1. Zoom (Two Hands)
        pointing_hands = [h for h in hands_data if h["gesture"] == GestureType.POINTING]
        if len(pointing_hands) >= 2:
            self.is_interacting = True
            p1 = np.array(pointing_hands[0]["proj_pos"])
            p2 = np.array(pointing_hands[1]["proj_pos"])
            dist = np.linalg.norm(p1 - p2)

            if self.zoom_gesture_start_time == 0:
                self.zoom_gesture_start_time = current_time
            elif current_time - self.zoom_gesture_start_time > config_vars.ZOOM_DELAY:
                # Calculate screen center (Fixed Pivot)
                screen_cx = self.config.width / 2
                screen_cy = self.config.height / 2

                if self.zoom_start_dist is None:
                    self.zoom_start_dist = dist
                    self.zoom_start_level = self.map_system.state.zoom
                    # Calculate world coordinate under the screen center
                    wx, wy = self.map_system.screen_to_world(screen_cx, screen_cy)
                    self.zoom_start_world_center = (wx, wy)
                else:
                    factor = dist / self.zoom_start_dist
                    new_zoom = self.zoom_start_level * factor
                    
                    # Apply new zoom using robust pivot logic
                    wx, wy = self.zoom_start_world_center
                    self.map_system.set_zoom_around_pivot(new_zoom, screen_cx, screen_cy, wx, wy)
        else:
            self.zoom_gesture_start_time = 0
            self.zoom_start_dist = None
            self.zoom_start_world_center = None

        # 2. Pan (Fist)
        if self.zoom_start_dist is None:
            if hands_data and hands_data[0]["gesture"] == config_vars.PAN_GESTURE:
                self.is_interacting = True
                pos = hands_data[0]["proj_pos"]
                if self.last_cursor_pos is not None:
                    dx = pos[0] - self.last_cursor_pos[0]
                    dy = pos[1] - self.last_cursor_pos[1]
                    self.map_system.pan(dx, dy)
                self.last_cursor_pos = pos
            else:
                self.last_cursor_pos = None

        # 3. Confirm (Victory)
        if hands_data and hands_data[0]["gesture"] == GestureType.VICTORY:
             # Debounce? Let's require hold?
             # For now, instant confirm is risky. Let's reuse SUMMON_TIME logic or similar.
             if self.summon_gesture_start_time == 0:
                 self.summon_gesture_start_time = current_time
             elif current_time - self.summon_gesture_start_time > 1.0: # 1 sec hold
                 # Save Config
                 filename = self.svg_loader.filename if self.svg_loader else "unknown"
                 
                 # The current state IS the Base Scale
                 new_base_scale = self.map_system.state.zoom
                 ppi = self.map_config.get_ppi()
                 
                 # Derive grid spacing from current alignment
                 derived_spacing = (ppi * self.calib_map_grid_size_inches) / new_base_scale
                 
                 print(f"Calibrated {filename}: Spacing={derived_spacing:.1f}, Unit={self.calib_map_grid_size_inches}in")
                 
                 self.map_config.save_map_grid_config(
                     filename,
                     grid_spacing_svg=derived_spacing,
                     grid_origin_svg_x=0.0, # Origin logic not implemented yet
                     grid_origin_svg_y=0.0,
                     physical_unit_inches=self.calib_map_grid_size_inches,
                     scale_factor_1to1=new_base_scale
                 )
                 
                 # Restore User View
                 if self.saved_map_state:
                     self.map_system.state = self.saved_map_state
                     # Update Zoom: Preserve User Zoom Level relative to new base
                     old_base = self.current_base_scale
                     if old_base > 0:
                         user_zoom_factor = self.map_system.state.zoom / old_base
                         self.map_system.state.zoom = user_zoom_factor * new_base_scale
                     self.saved_map_state = None
                     
                 self.current_base_scale = new_base_scale
                 self.mode = AppMode.MENU
                 self.summon_gesture_start_time = 0
        else:
            self.summon_gesture_start_time = 0
            
        return []

    def _draw_calib_map_grid_overlay(self, image):
        # Draw physical grid based on PPI
        ppi = self.map_config.get_ppi()
        physical_unit = self.calib_map_grid_size_inches
        step = int(ppi * physical_unit)
        
        if step > 0:
            h, w = image.shape[:2]
            cx, cy = w // 2, h // 2
            
            # Dimmer Green
            grid_color = (0, 120, 0)
            cross_size = 10

            # Draw Center Crosshairs (Full lines, but dimmer)
            cv2.line(image, (cx, 0), (cx, h), (0, 0, 0), 3) # Outline
            cv2.line(image, (cx, 0), (cx, h), grid_color, 1)
            cv2.line(image, (0, cy), (w, cy), (0, 0, 0), 3) # Outline
            cv2.line(image, (0, cy), (w, cy), grid_color, 1)
            
            # Draw Crosses at intersections
            for x in range(cx % step, w, step):
                for y in range(cy % step, h, step):
                    # Skip center (already drawn as full lines)
                    if x == cx and y == cy:
                        continue
                        
                    # Horizontal part of cross
                    cv2.line(image, (x - cross_size, y), (x + cross_size, y), (0, 0, 0), 3)
                    cv2.line(image, (x - cross_size, y), (x + cross_size, y), grid_color, 1)
                    # Vertical part of cross
                    cv2.line(image, (x, y - cross_size), (x, y + cross_size), (0, 0, 0), 3)
                    cv2.line(image, (x, y - cross_size), (x, y + cross_size), grid_color, 1)

        cv2.putText(
            image,
            f"Set Scale: Align Map to {physical_unit} inch Grid",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            image,
            "Confirm: VICTORY (Hold 1s)",
            (50, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

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
                    cv2.line(image, (x, 0), (x, h), (0, 255, 0), 1)
                # Draw horizontal lines
                for y in range(0, h, step):
                    cv2.line(image, (0, y), (w, y), (0, 255, 0), 1)

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
        
        # Check for uncalibrated grid
        if self.svg_loader:
             entry = self.map_config.data.maps.get(self.svg_loader.filename)
             if not entry or entry.grid_spacing_svg <= 0:
                 cv2.putText(
                     image,
                     "GRID UNCALIBRATED - Use 'Set Scale'",
                     (50, 100),
                     cv2.FONT_HERSHEY_SIMPLEX,
                     1,
                     (0, 0, 255),
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
