import pytest
import numpy as np
from light_map.map.map_system import MapSystem


@pytest.fixture
def map_system():
    from light_map.core.common_types import AppConfig

    config = AppConfig(width=1000, height=1000, projector_matrix=np.eye(3))
    return MapSystem(config)


def test_undo_simple(map_system):
    # Initial state S0
    s0 = map_system.state.to_viewport()

    # Change state to S1
    map_system.push_state()  # Save S0
    map_system.pan(100, 100)

    assert map_system.state.x == 100.0

    # Undo to S0
    map_system.undo()
    assert map_system.state.x == s0.x
    assert map_system.state.y == s0.y
    assert map_system.state.zoom == s0.zoom


def test_redo_simple(map_system):
    # Initial S0
    s0 = map_system.state.to_viewport()

    map_system.push_state()  # Save S0
    map_system.pan(100, 100)
    s1 = map_system.state.to_viewport()

    map_system.undo()
    assert map_system.state.x == s0.x

    map_system.redo()
    assert map_system.state.x == s1.x
    assert map_system.state.y == s1.y
    assert map_system.state.zoom == s1.zoom


def test_multiple_undo_redo(map_system):
    # S0 -> S1 -> S2
    map_system.push_state()
    map_system.pan(100, 0)

    map_system.push_state()
    map_system.pan(0, 100)

    assert map_system.state.x == 100
    assert map_system.state.y == 100

    map_system.undo()  # To S1
    assert map_system.state.x == 100
    assert map_system.state.y == 0

    map_system.undo()  # To S0
    assert map_system.state.x == 0
    assert map_system.state.y == 0

    map_system.redo()  # To S1
    assert map_system.state.x == 100
    assert map_system.state.y == 0

    map_system.redo()  # To S2
    assert map_system.state.x == 100
    assert map_system.state.y == 100


def test_redo_stack_cleared_on_new_push(map_system):
    map_system.push_state()  # S0
    map_system.pan(100, 0)  # S1

    map_system.undo()  # Back to S0
    assert map_system.can_redo()

    map_system.push_state()  # Save S0 again (or just overwrite?)
    # Actually, push_state should probably be called BEFORE a change.
    map_system.pan(0, 100)  # S2

    # Redo stack should be cleared
    assert not map_system.can_redo()
    map_system.redo()  # Should not raise IndexError anymore

def test_can_undo_redo_flags(map_system):
    assert not map_system.can_undo()
    assert not map_system.can_redo()

    map_system.push_state()
    map_system.pan(10, 10)

    assert map_system.can_undo()
    assert not map_system.can_redo()

    map_system.undo()
    assert not map_system.can_undo()
    assert map_system.can_redo()
