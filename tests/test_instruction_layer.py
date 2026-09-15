
import numpy as np
import pytest

from light_map.core.common_types import AppConfig, CalibrationState
from light_map.rendering.layers.calibration_layer import CalibrationLayer
from light_map.rendering.layers.instruction_layer import InstructionLayer
from light_map.state.world_state import WorldState


@pytest.fixture
def config():
    return AppConfig(width=800, height=600, projector_matrix=np.eye(3))


@pytest.fixture
def state():
    return WorldState()


def test_instruction_layer_empty_by_default(state, config):
    layer = InstructionLayer(state, config)
    patches = layer._generate_patches(0.0)
    assert patches == []


def test_instruction_layer_renders_from_calibration_state(state, config):
    layer = InstructionLayer(state, config)
    state.calibration = CalibrationState(
        stage="ALIGNMENT",
        instruction_text="Align pattern in view of both cameras.",
    )

    patches = layer._generate_patches(0.0)
    assert len(patches) == 1
    patch = patches[0]
    assert patch.width == 800
    assert patch.height == 600
    # Must have non-zero alpha pixels for rendered text
    assert np.any(patch.data[:, :, 3] > 0)


def test_instruction_layer_renders_from_explicit_attributes(config):
    layer = InstructionLayer(
        config=config,
        stage="TEST_STAGE",
        instructions="Hold Victory gesture.",
    )

    patches = layer._generate_patches(0.0)
    assert len(patches) == 1
    patch = patches[0]
    assert np.any(patch.data[:, :, 3] > 0)


def test_calibration_layer_render_instructions_flag(state, config):
    state.calibration = CalibrationState(
        stage="ALIGNMENT",
        instruction_text="Test instructions",
    )

    layer_with_text = CalibrationLayer(state, config, render_instructions=True)
    patches_with = layer_with_text._generate_patches(0.0)
    assert len(patches_with) == 1

    layer_without_text = CalibrationLayer(state, config, render_instructions=False)
    patches_without = layer_without_text._generate_patches(0.0)
    assert len(patches_without) == 1

    # Both render, but without_text will not render the instruction overlay text
    # Checking that the flag is respected
    assert layer_without_text.render_instructions is False
    assert layer_with_text.render_instructions is True
