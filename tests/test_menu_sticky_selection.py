import pytest

from light_map.core.common_types import GestureType, MenuItem
from light_map.menu.menu_system import MenuSystem, MenuSystemState


@pytest.fixture
def menu_system():
    # Simple menu: 3 items
    items = [MenuItem(f"Item {i}", action_id=f"ACT_{i}") for i in range(3)]
    root = MenuItem("Root", children=items)

    class MockTime:
        def __call__(self):
            return 1000.0

    ms = MenuSystem(800, 600, root, time_provider=MockTime())
    ms.state = MenuSystemState.ACTIVE
    return ms


def test_sticky_hover_logic(menu_system):
    ms = menu_system

    # Get layout to know where items are
    items, rects = ms._calculate_layout()
    assert len(rects) >= 2

    # 1. Hover Item 0
    r0 = rects[0]
    cx0 = r0[0] + 10
    cy0 = r0[1] + 10

    state = ms.update(cx0, cy0, GestureType.POINTING)
    assert state.hovered_item_index == 0
    assert ms.last_hovered_index == 0

    # 2. Move to "Void" (outside any item)
    # Assume 0,0 is void (layout is centered usually)
    state = ms.update(0, 0, GestureType.POINTING)

    # Should still be 0 (Sticky)
    assert state.hovered_item_index == 0
    assert ms.last_hovered_index == 0

    # 3. Hover Item 1
    r1 = rects[1]
    cx1 = r1[0] + 10
    cy1 = r1[1] + 10

    state = ms.update(cx1, cy1, GestureType.POINTING)
    assert state.hovered_item_index == 1
    assert ms.last_hovered_index == 1


def test_trigger_uses_sticky_selection(menu_system):
    ms = menu_system
    items, rects = ms._calculate_layout()

    # 1. Hover Item 0
    r0 = rects[0]
    cx0 = r0[0] + 10
    cy0 = r0[1] + 10
    ms.update(cx0, cy0, GestureType.POINTING)
    assert ms.last_hovered_index == 0

    # 2. Move cursor away (drift) and trigger
    # Pinning logic uses history, let's assume pinning happens at the DRIFT location
    # but the TRIGGER checks last_hovered_index.

    # Wait, _trigger_selection logic was changed to use last_hovered_index.
    # But Pinning logic in update() sets ms.pinned_cursor based on history.
    # We need to simulate the pinning sequence.

    # Step A: Select Gesture starts
    ms.update(0, 0, GestureType.CLOSED_FIST)  # Cursor at 0,0 (void)

    # Step B: Wait for priming
    # Mock time advancement?
    # We can just call _trigger_selection directly to test the logic

    # Ensure last_hovered_index is 0
    assert ms.last_hovered_index == 0

    action = ms._trigger_selection()
    assert action == "ACT_0"


def test_navigation_resets_sticky(menu_system):
    ms = menu_system
    # Give Item 0 a child to enter
    child = MenuItem("Child", action_id="CHILD_ACT")
    ms.root.children[0].children = [child]

    # Hover Item 0
    items, rects = ms._calculate_layout()
    r0 = rects[0]
    ms.update(r0[0] + 10, r0[1] + 10, GestureType.POINTING)
    assert ms.last_hovered_index == 0

    # Trigger Enter
    ms._trigger_selection()

    # Should have entered submenu and reset selection
    assert ms.current_node.title == "Item 0"
    assert ms.last_hovered_index is None
