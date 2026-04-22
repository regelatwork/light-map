import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.state.world_state import WorldState
from light_map.rendering.layers.tactical_overlay_layer import TacticalOverlayLayer
from light_map.core.common_types import Token
from light_map.map.map_system import MapSystem
from light_map.visibility.visibility_engine import VisibilityEngine


@pytest.fixture
def mock_state():
    state = WorldState()
    state.inspected_token_id = 1
    # Full visibility mask (100x100)
    mask = np.full((100, 100), 255, dtype=np.uint8)
    state.inspected_token_mask = mask
    return state


@pytest.fixture
def mock_map_system():
    ms = MagicMock(spec=MapSystem)
    ms.world_to_screen.side_effect = lambda x, y: (
        x * 2,
        y * 2,
    )  # Simple scale for testing
    ms.config = MagicMock()
    ms.config.projector_ppi = 96.0
    ms.ghost_tokens = []
    return ms


@pytest.fixture
def mock_engine():
    ve = MagicMock(spec=VisibilityEngine)
    ve.svg_to_mask_scale = 1.0
    return ve


def test_tactical_overlay_clear_los(mock_state, mock_map_system, mock_engine):
    """Verifies that a CLEAR LOS label is generated when there is no cover bonus."""
    layer = TacticalOverlayLayer(mock_state, mock_map_system, mock_engine)

    # Token 2 is visible
    token = Token(id=2, world_x=50, world_y=50)
    mock_state.tokens = [token]
    # No tactical bonuses set explicitly, but required for the layer to process it
    mock_state.tactical_bonuses = {2: (0, 0)}

    patches = layer._generate_patches(0.0)

    assert len(patches) == 1
    patch = patches[0]
    assert patch.x == (50 * 2) - (patch.width // 2)
    assert patch.y == (50 * 2) + 48 + 5


def test_tactical_overlay_cover_bonus(mock_state, mock_map_system, mock_engine):
    """Verifies that a cover bonus label is generated."""
    layer = TacticalOverlayLayer(mock_state, mock_map_system, mock_engine)

    token = Token(id=2, world_x=50, world_y=50)
    mock_state.tokens = [token]
    mock_state.tactical_bonuses = {2: (4, 2)}

    patches = layer._generate_patches(0.0)
    assert len(patches) == 1


def test_tactical_overlay_total_cover(mock_state, mock_map_system, mock_engine):
    """Verifies that a TOTAL COVER label is generated."""
    layer = TacticalOverlayLayer(mock_state, mock_map_system, mock_engine)

    token = Token(id=2, world_x=50, world_y=50)
    mock_state.tokens = [token]
    mock_state.tactical_bonuses = {2: (-1, -1)}

    patches = layer._generate_patches(0.0)
    assert len(patches) == 1


def test_tactical_overlay_invisible_token(mock_state, mock_map_system, mock_engine):
    """Verifies that no label is generated for an invisible token."""
    layer = TacticalOverlayLayer(mock_state, mock_map_system, mock_engine)

    # Token 2 is outside the mask (at 150, 150)
    token = Token(id=2, world_x=150, world_y=150)
    mock_state.tokens = [token]

    # Empty the mask
    mock_state.inspected_token_mask = np.zeros((100, 100), dtype=np.uint8)

    patches = layer._generate_patches(0.0)
    assert len(patches) == 0


def test_tactical_overlay_skips_inspected_token(
    mock_state, mock_map_system, mock_engine
):
    """Verifies that the source (inspected) token does not get a label."""
    layer = TacticalOverlayLayer(mock_state, mock_map_system, mock_engine)

    token = Token(id=1, world_x=50, world_y=50)  # Same ID as inspected
    mock_state.tokens = [token]

    patches = layer._generate_patches(0.0)
    assert len(patches) == 0
