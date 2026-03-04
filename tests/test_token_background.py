import numpy as np
from unittest.mock import MagicMock, patch
from light_map.display_utils import draw_text_with_background


def test_draw_text_with_background_calls_rectangle_and_puttext():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    text = "Hello"
    pos = (10, 50)

    # We want to verify that cv2.rectangle and cv2.putText are called
    # and that some pixels in the image changed (for the background)

    # Use a solid alpha to make it easier to detect change
    draw_text_with_background(img, text, pos, alpha=1.0, bg_color=(255, 0, 0))

    # Check if any pixels changed to (255, 0, 0) in the area
    # (getTextSize might vary slightly by platform, but it should be around the pos)
    assert np.any(np.all(img == [255, 0, 0], axis=-1))


def test_draw_text_with_background_clipping():
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    # Draw text near the edge
    draw_text_with_background(
        img, "Long text that will definitely be clipped", (40, 40)
    )
    # Should not crash


@patch("light_map.vision.overlay_renderer.draw_text_with_background")
def test_overlay_renderer_uses_background_text(mock_draw_bg):
    # For simplicity, let's just mock what we need
    from light_map.vision.overlay_renderer import OverlayRenderer
    from light_map.common_types import Token
    from light_map.map_config import ResolvedToken

    context = MagicMock()
    context.map_config_manager.get_ppi.return_value = 100.0
    context.map_config_manager.resolve_token_profile.return_value = ResolvedToken(
        name="Hero", type="PC", size=1, height_mm=25.0, is_known=True
    )
    context.map_system.world_to_screen.return_value = (500, 500)
    context.map_system.ghost_tokens = [Token(id=1, world_x=5, world_y=5)]
    context.map_system.svg_loader = None

    renderer = OverlayRenderer(context)

    patches = renderer.draw_ghost_tokens(lambda: 0)
    assert len(patches) == 1

    # Verify draw_text_with_background was called for the name
    # The position is now relative to the patch buffer
    mock_draw_bg.assert_called()
    found = False
    for call in mock_draw_bg.call_args_list:
        args, _ = call
        if args[1] == "Hero":
            found = True
            break
    assert found
