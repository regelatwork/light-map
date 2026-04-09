from unittest.mock import MagicMock
from light_map.menu.menu_builder import build_root_menu, build_map_actions_submenu
from light_map.map.map_config import MapEntry


def test_build_map_actions_submenu():
    filename = "/maps/test.svg"
    items = build_map_actions_submenu(filename, has_session=True)

    assert len(items) == 4
    assert items[0].title == "Load Map"
    assert items[0].action_id == "LOAD_MAP|/maps/test.svg"
    assert items[1].title == "Load Session"
    assert items[1].action_id == "LOAD_SESSION|/maps/test.svg"

    items_no_session = build_map_actions_submenu(filename, has_session=False)
    assert len(items_no_session) == 3
    assert not any(i.title == "Load Session" for i in items_no_session)


def test_build_root_menu():
    mock_config = MagicMock()
    mock_config.data.maps = {"/maps/A.svg": MapEntry(), "/maps/B.svg": MapEntry()}

    # Mock status
    def get_status(filename):
        if filename == "/maps/A.svg":
            return {"calibrated": True, "has_session": True}
        return {"calibrated": False, "has_session": False}

    mock_config.get_map_status.side_effect = get_status

    root = build_root_menu(mock_config)

    # Find Maps submenu
    # It should be the second item (index 1) after "< Close"
    maps_menu = root.children[1]
    assert maps_menu.title == "Maps"

    # Check children
    # Expect 3 children: A, B, Scan
    assert len(maps_menu.children) == 3

    # Check A (Calibrated + Session) -> "(*) A.svg"
    item_a = maps_menu.children[0]
    # Note: Sorting is case-insensitive usually, here just alphabetical
    assert "A.svg" in item_a.title
    assert "(*)" in item_a.title

    # Check B (Uncalibrated) -> "(!) B.svg"
    item_b = maps_menu.children[1]
    assert "B.svg" in item_b.title
    assert "(!)" in item_b.title

    # Check Scan
    item_scan = maps_menu.children[2]
    assert item_scan.title == "Scan for Maps"
    assert item_scan.action_id == "SCAN_FOR_MAPS"
