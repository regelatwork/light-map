# Hierarchical Menu System

The `hand_tracker.py` script features a hierarchical menu system, allowing for interactive control using hand gestures.

## Menu Interaction

- **Summon Menu**: Perform the **Victory** (Peace sign) gesture and hold it for a short duration (`SUMMON_TIME` defined in `menu_config.py`). The menu will appear on the projector screen.
- **Navigate & Hover**: Once the menu is active, move your **index fingertip** to hover over different menu items.
- **Select Item**: With an item hovered, perform the **Closed Fist** gesture and hold it for a short duration (`PRIMING_TIME` defined in `menu_config.py`). This will select the item.
  - If the item has sub-menus, you will navigate into the sub-menu.
  - If the item is an action, the action will be triggered, and if `should_close_on_trigger` is true for that item, the menu will close.
- **Calibrate**: Select "Settings" -> "Calibrate" to trigger the projector calibration sequence without leaving the application. The new calibration will be automatically saved and reloaded.
- **Navigate Back**: Select the "< Back" item to return to the previous menu level.
- **Dismiss Menu**: Select the "< Close" item at the top of the menu to close it.
- **Quit Application**: Select the "Quit" item at the bottom of the menu to exit the application.

## Configuration

The menu structure and interaction timings are defined in `src/light_map/menu_config.py`.
