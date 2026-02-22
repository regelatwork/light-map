import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import Token, SceneId
from light_map.map_config import MapConfigManager, ResolvedToken

@pytest.fixture
def app_config():
    matrix = np.eye(3, dtype=np.float32)
    mock_map_config = MagicMock(spec=MapConfigManager)
    mock_map_config.data = MagicMock()
    mock_map_config.data.maps = {}
    mock_map_config.get_map_status.return_value = {"calibrated": False, "has_session": False}
    mock_map_config.get_ppi.return_value = 96.0
    mock_map_config.get_map_viewport.return_value = MagicMock()
    
    config = AppConfig(width=1000, height=1000, projector_matrix=matrix, map_search_patterns=[])
    return config, mock_map_config

@pytest.fixture
def app(app_config):
    _app_config, mock_map_config = app_config
    with (
        patch("light_map.interactive_app.MenuScene"),
        patch("light_map.interactive_app.ScanningScene"),
        patch("light_map.interactive_app.FlashCalibrationScene"),
        patch("light_map.interactive_app.MapGridCalibrationScene"),
        patch("light_map.interactive_app.PpiCalibrationScene"),
    ):
        _app = InteractiveApp(_app_config)
    _app.app_context.map_config_manager = mock_map_config
    _app.map_config = mock_map_config
    return _app

def test_draw_ghost_tokens_unknown(app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True
    
    # One known, one unknown
    app.map_system.ghost_tokens = [
        Token(id=1, world_x=100, world_y=100),
        Token(id=2, world_x=200, world_y=200)
    ]
    
    # Mock world_to_screen
    app.map_system.world_to_screen = MagicMock(side_effect=[(100, 100), (200, 200)])
    
    # Mock resolve_token_profile
    app.app_context.map_config_manager.resolve_token_profile.side_effect = [
        ResolvedToken(name="Fighter", type="PC", size=1, height_mm=10.0, is_known=True),
        ResolvedToken(name="Unknown Token #2", type="NPC", size=1, height_mm=10.0, is_known=False)
    ]
    
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    
    with (
        patch("cv2.circle") as mock_circle,
        patch("cv2.putText") as mock_putText,
        patch("light_map.interactive_app.draw_dashed_circle") as mock_dashed_circle
    ):
        app._draw_ghost_tokens(frame)
        
        # Known token (ID 1) should use cv2.circle
        mock_circle.assert_called_once()
        args, _ = mock_circle.call_args
        assert args[1] == (100, 100) # center
        
        # Unknown token (ID 2) should use draw_dashed_circle
        mock_dashed_circle.assert_called_once()
        args, _ = mock_dashed_circle.call_args
        assert args[1] == (200, 200) # center
        
        # Unknown token should also have a "?" drawn
        found_q = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "?":
                found_q = True
                assert args[2][0] == 200 - 8 # Approximate X pos
                break
        assert found_q, "Question mark not found for unknown token"

def test_draw_ghost_tokens_duplicate(app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True
    
    # One primary, one duplicate
    app.map_system.ghost_tokens = [
        Token(id=10, world_x=100, world_y=100, is_duplicate=False),
        Token(id=10, world_x=300, world_y=300, is_duplicate=True)
    ]
    
    # Mock world_to_screen
    app.map_system.world_to_screen = MagicMock(side_effect=[(100, 100), (300, 300)])
    
    # Mock resolve_token_profile
    app.app_context.map_config_manager.resolve_token_profile.return_value = \
        ResolvedToken(name="Goblin", type="NPC", size=1, height_mm=10.0, is_known=True)
    
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    
    with (
        patch("cv2.circle") as mock_circle,
        patch("cv2.putText") as mock_putText,
        patch("light_map.interactive_app.draw_dashed_circle") as mock_dashed_circle
    ):
        app._draw_ghost_tokens(frame)
        
        # Primary token (ID 10, pos 100,100) should use cv2.circle
        # We might have multiple calls to cv2.circle if there are multiple tokens, 
        # but here we only have one non-duplicate.
        found_primary = False
        for call in mock_circle.call_args_list:
            args, _ = call
            if args[1] == (100, 100):
                found_primary = True
                break
        assert found_primary
        
        # Duplicate token (ID 10, pos 300,300) should use draw_dashed_circle
        mock_dashed_circle.assert_called_once()
        args, _ = mock_dashed_circle.call_args
        assert args[1] == (300, 300) # center
        
        # Duplicate token should also have "DUPLICATE" text drawn
        found_dup_text = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "DUPLICATE":
                found_dup_text = True
                assert args[2][1] > 300 # Should be below the center
                break
        assert found_dup_text, "'DUPLICATE' label not found for duplicate token"
