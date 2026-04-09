import pytest
from light_map.menu.menu_system import MenuSystem, MenuSystemState
from light_map.core.common_types import MenuItem, MenuActions

# Override MAX_VISIBLE_ITEMS for testing if possible, or assume 8.
# Since it's imported, we can patch it or rely on logic.
# The logic uses whatever is imported.
# Let's assume default 8 for now, but create enough items to force paging.


@pytest.fixture
def paged_menu_system():
    # Create 20 items
    # Page size = 8 - 2 = 6.
    # Page 0: 0-5 + Next (7 slots used)
    # Page 1: Prev + 6-11 + Next (8 slots used)
    # Page 2: Prev + 12-17 + Next (8 slots used)
    # Page 3: Prev + 18-19 (3 slots used)

    items = [MenuItem(f"Item {i}", action_id=f"ACT_{i}") for i in range(20)]
    root = MenuItem("Root", children=items)

    # Mock Time
    class MockTime:
        def __call__(self):
            return 1000.0

    return MenuSystem(1000, 1000, root, time_provider=MockTime())


def test_pagination_flow(paged_menu_system):
    ms = paged_menu_system
    ms.state = MenuSystemState.ACTIVE

    # --- Page 0 ---
    # Should see Items 0 to 5 (6 items) + Next Page
    # Total 7 items shown. (MAX=8)

    items, rects = ms._calculate_layout()
    titles = [i.title for i in items]

    assert "Item 0" in titles
    assert "Item 5" in titles
    assert "Item 6" not in titles
    assert "Next Page >" in titles
    assert "< Prev Page" not in titles

    # Trigger Next Page
    # Find index of Next Page
    next_idx = next(
        i for i, item in enumerate(items) if item.action_id == MenuActions.PAGE_NEXT
    )
    from light_map.core.common_types import GestureType

    rect = rects[next_idx]
    cx, cy = rect[0] + 10, rect[1] + 10

    # Must update hover state for sticky selection
    ms.update(cx, cy, GestureType.POINTING)
    ms.pinned_cursor = (cx, cy)
    ms._trigger_selection()

    assert ms.page_index == 1

    # --- Page 1 ---
    # Should see Prev + Items 6 to 11 (6 items) + Next
    items, rects = ms._calculate_layout()
    titles = [i.title for i in items]

    assert "< Prev Page" in titles
    assert "Item 6" in titles
    assert "Item 11" in titles
    assert "Item 12" not in titles
    assert "Next Page >" in titles

    # Trigger Next Page again -> Page 2
    ms.page_index = 2

    # --- Page 2 ---
    # Items 12-17
    items, rects = ms._calculate_layout()
    titles = [i.title for i in items]
    assert "Item 12" in titles
    assert "Item 17" in titles

    # Trigger Next Page -> Page 3 (Last)
    ms.page_index = 3

    # --- Page 3 ---
    # Items 18-19. No Next.
    items, rects = ms._calculate_layout()
    titles = [i.title for i in items]

    assert "< Prev Page" in titles
    assert "Item 18" in titles
    assert "Item 19" in titles
    assert "Next Page >" not in titles

    # Trigger Prev Page -> Page 2
    prev_idx = next(
        i for i, item in enumerate(items) if item.action_id == MenuActions.PAGE_PREV
    )
    from light_map.core.common_types import GestureType

    rect = rects[prev_idx]
    cx, cy = rect[0] + 10, rect[1] + 10

    # Must update hover state for sticky selection
    ms.update(cx, cy, GestureType.POINTING)
    ms.pinned_cursor = (cx, cy)
    ms._trigger_selection()

    assert ms.page_index == 2
