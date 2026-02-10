from light_map.menu_config import ROOT_MENU
from light_map.common_types import MenuActions

def test_root_menu_structure():
    # 1. Verify Top Item is Close/Back
    top_item = ROOT_MENU.children[0]
    assert top_item.title == "< Close"
    assert top_item.action_id == MenuActions.CLOSE_MENU
    assert top_item.should_close_on_trigger
    
    # 2. Verify Bottom Item is Quit
    bottom_item = ROOT_MENU.children[-1]
    assert bottom_item.title == "Quit"
    assert bottom_item.action_id == MenuActions.EXIT
    assert bottom_item.should_close_on_trigger
    
    # 3. Verify other items exist
    titles = [c.title for c in ROOT_MENU.children]
    assert "Map Controls" in titles
    assert "Map Settings" in titles
    assert "Calibrate" in titles
    assert "Options" in titles

def test_map_settings_submenu():
    # Find Map Settings
    map_settings = next(c for c in ROOT_MENU.children if c.title == "Map Settings")
    
    # Verify children
    sub_titles = [c.title for c in map_settings.children]
    assert "Rotate CW" in sub_titles
    assert "Rotate CCW" in sub_titles
    assert "Reset View" in sub_titles
    assert "Calibrate Scale" in sub_titles
