import os
from typing import List, Optional
from light_map.common_types import MenuItem, MenuActions
from light_map.map_config import MapConfigManager


def build_map_actions_submenu(filename: str, has_session: bool) -> List[MenuItem]:
    items = []

    # Load Map
    items.append(
        MenuItem(
            title="Load Map",
            action_id=f"LOAD_MAP|{filename}",
            should_close_on_trigger=True,
        )
    )

    # Load Session
    if has_session:
        items.append(
            MenuItem(
                title="Load Session",
                action_id=f"LOAD_SESSION|{filename}",
                should_close_on_trigger=True,
            )
        )

    # Calibrate Scale
    items.append(
        MenuItem(
            title="Calibrate Scale",
            action_id=f"CALIBRATE_MAP|{filename}",
            should_close_on_trigger=True,
        )
    )

    # Forget Map
    items.append(
        MenuItem(
            title="Forget Map",
            action_id=f"FORGET_MAP|{filename}",
            should_close_on_trigger=True,
        )
    )

    return items


def build_root_menu(
    map_config: MapConfigManager, selected_door: Optional[str] = None
) -> MenuItem:

    # Build Maps Submenu
    map_items = []

    # Get maps and sort alphabetically by filename
    known_maps = sorted(
        map_config.data.maps.keys(), key=lambda x: os.path.basename(x).lower()
    )

    for filename in known_maps:
        status = map_config.get_map_status(filename)
        is_calibrated = status["calibrated"]
        has_session = status["has_session"]

        # Icon Logic
        # Priority: Session (*) > Uncalibrated (!) > Normal
        # Or maybe combine?
        # Design doc said:
        # (!) : Uncalibrated
        # (*) : Saved Session
        # (None) : Ready

        prefix = ""
        if not is_calibrated:
            prefix = "(!) "
        if has_session:
            prefix += "(*) "

        display_name = f"{prefix}{os.path.basename(filename)}"

        # Create Item with Submenu
        map_items.append(
            MenuItem(
                title=display_name,
                children=build_map_actions_submenu(filename, has_session),
            )
        )

    # Add Scan Option at the end
    map_items.append(
        MenuItem(
            title="Scan for Maps",
            action_id="SCAN_FOR_MAPS",
            should_close_on_trigger=True,
        )
    )

    maps_menu = MenuItem(title="Maps", children=map_items)

    # Construct Root
    # We replicate the structure from menu_config.py but inject maps_menu
    root = MenuItem(
        title="Main Menu",
        children=[
            MenuItem(
                title="< Close",
                action_id=MenuActions.CLOSE_MENU,
                should_close_on_trigger=True,
            ),
            maps_menu,  # NEW
            MenuItem(
                title="Sync Vision",
                action_id=MenuActions.SYNC_VISION,
                should_close_on_trigger=True,
            ),
        ]
        + (
            [
                MenuItem(
                    title=f"Toggle Door ({selected_door})",
                    action_id=MenuActions.TOGGLE_DOOR,
                    should_close_on_trigger=True,
                )
            ]
            if selected_door
            else []
        )
        + [
            MenuItem(
                title="Map Settings",
                children=[
                    MenuItem(
                        title="Rotate CW",
                        action_id=MenuActions.ROTATE_CW,
                        should_close_on_trigger=False,
                    ),
                    MenuItem(
                        title="Rotate CCW",
                        action_id=MenuActions.ROTATE_CCW,
                        should_close_on_trigger=False,
                    ),
                    MenuItem(
                        title="Reset View",
                        action_id=MenuActions.RESET_VIEW,
                        should_close_on_trigger=False,
                    ),
                    MenuItem(
                        title="Zoom 1:1",
                        action_id=MenuActions.RESET_ZOOM,
                        should_close_on_trigger=False,
                    ),
                    MenuItem(
                        title="Set Scale",
                        action_id=MenuActions.SET_MAP_SCALE,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="Calibrate PPI",
                        action_id=MenuActions.CALIBRATE_SCALE,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="Reset Fog of War",
                        action_id=MenuActions.RESET_FOW,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="GM: Toggle Fog of War",
                        action_id=MenuActions.TOGGLE_FOW,
                        should_close_on_trigger=False,
                    ),
                ],
            ),
            MenuItem(
                title="Map Interaction Mode",
                action_id=MenuActions.MAP_CONTROLS,
                should_close_on_trigger=True,
            ),
            MenuItem(
                title="Calibration",
                children=[
                    MenuItem(
                        title="1. Camera Intrinsics",
                        action_id=MenuActions.CALIBRATE_INTRINSICS,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="2. Projector Homography",
                        action_id=MenuActions.CALIBRATE_PROJECTOR,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="3. Physical PPI",
                        action_id=MenuActions.CALIBRATE_PPI,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="4. Camera Extrinsics",
                        action_id=MenuActions.CALIBRATE_EXTRINSICS,
                        should_close_on_trigger=True,
                    ),
                ],
            ),
            MenuItem(
                title="Session",
                children=[
                    MenuItem(
                        title="Scan & Save",
                        action_id=MenuActions.SCAN_SESSION,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="Calibrate Flash",
                        action_id=MenuActions.CALIBRATE_FLASH,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title="Load Last Session",
                        action_id=MenuActions.LOAD_SESSION,
                        should_close_on_trigger=True,
                    ),
                    MenuItem(
                        title=f"Algorithm: {map_config.get_detection_algorithm()}",
                        action_id=MenuActions.SCAN_ALGORITHM,
                        should_close_on_trigger=False,
                    ),
                ],
            ),
            MenuItem(
                title="Options",
                children=[
                    MenuItem(
                        title="Toggle Debug",
                        action_id=MenuActions.TOGGLE_DEBUG_MODE,
                        should_close_on_trigger=False,
                    ),
                    MenuItem(
                        title="Masking",
                        children=[
                            MenuItem(
                                title=f"Projection Masking: {'ON' if map_config.data.global_settings.enable_hand_masking else 'OFF'}",
                                action_id=MenuActions.TOGGLE_HAND_MASKING,
                                should_close_on_trigger=False,
                            ),
                            MenuItem(
                                title="GM Position",
                                children=[
                                    MenuItem(
                                        title=f"{'[*] ' if map_config.data.global_settings.gm_position == pos else ''}{pos}",
                                        action_id=f"SET_GM_POSITION|{pos}",
                                        should_close_on_trigger=False,
                                    )
                                    for pos in [
                                        "None",
                                        "North",
                                        "South",
                                        "East",
                                        "West",
                                        "North West",
                                        "North East",
                                        "South West",
                                        "South East",
                                    ]
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            MenuItem(
                title="Quit", action_id=MenuActions.EXIT, should_close_on_trigger=True
            ),
        ],
    )

    return root
