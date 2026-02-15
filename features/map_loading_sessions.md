# Feature: Map Loading & Session Management

## Overview

This feature enhances the system's ability to manage multiple map files, providing a robust way to switch between maps, track their calibration status, and persist game sessions (token positions) for each map.

## Goals

1. **Centralized Map List**: Maintain a list of known map files (SVG, image) that persists across restarts.
1. **Dynamic Updates**: Automatically update the list when files are added via CLI or removed from disk.
1. **Status Indicators**: Visually denote which maps have:
   - **Scale/Grid Calibration**: Grid size and origin are set.
   - **Saved Sessions**: Active token placements saved.
1. **Session Persistence**: Save and load token configurations specific to each map.
1. **Streamlined UX**: Simplify the process of "Starting a New Game" vs "Continuing a Session".

## Detailed Design

### 1. CLI Arguments & Map Discovery

Replace the single `--map` argument with a more flexible `--maps` argument.

- **`--maps <path1>,<path2>,<glob*>`**: Adds the specified files or directories to the internal "Known Maps" list.
- **Discovery Behavior**:
  - The application (specifically `MapConfigManager`) uses `glob.glob()` to expand patterns provided in arguments.
  - It scans provided paths/globs for valid map files (`.svg`, `.png`, `.jpg`).
  - It adds found maps to `map_state.json` if they are new.
  - **Auto-Pruning**: Automatically removes any entries from `map_state.json` if the corresponding file no longer exists on disk during startup or when the "Scan for Maps" action is triggered.
  - Does *not* automatically load a map unless it was the `last_used_map`.

### 2. Map Configuration (`map_state.json`)

Extend the `MapEntry` schema to include:

- `last_seen`: Timestamp (ISO 8601 string) for metadata.
- `has_session`: Boolean indicating a saved session file exists (computed at runtime, not necessarily persisted).
- `grid_calibrated`: Boolean (derived from `grid_spacing_svg > 0`).

### 3. Menu System Updates

#### Dynamic Menu Injection

The `MenuSystem` currently uses a static `ROOT_MENU`. To support a dynamic list of maps, we will introduce a `MenuFactory` or a utility function `generate_map_menu(map_config: MapConfigManager) -> MenuItem`.

- **Action ID Convention**:
  - To pass parameters through the simple `action_id` string, we will use a pipe-delimited format: `ACTION_TYPE|PAYLOAD`.
  - Example: `LOAD_MAP|/home/user/maps/dungeon.svg`
  - Example: `CALIBRATE_MAP|/home/user/maps/cave.png`

#### Root Menu -> "Maps"

A new top-level menu item "Maps" replaces the direct "Load Map" action. It is populated dynamically at startup and refresh.

**Structure:**

- **Maps** (Parent Item)
  - **[List of Known Maps]**
    - *Sorting*: Alphabetical by filename.
    - *Format*: `[Icon] Map Name`
    - *Icons*:
      - `(!)` : Uncalibrated (Grid scale unknown)
      - `(*)` : Saved Session Available
      - (None) : Ready, no session.
    - *Action*: Opens the **Map Action Menu** (Sub-menu) for that specific map.
  - **Scan for Maps**:
    - *Action ID*: `SCAN_FOR_MAPS`
    - *Behavior*: Explicitly re-scans known directories/arguments for new files and refreshes the menu.

#### Map Action Menu (Sub-menu)

When a map is selected, a new submenu is generated for it.

1. **Load Map** (Default):
   - *Action ID*: `LOAD_MAP|<filename>`
   - *Behavior*: Loads map, resets tokens (if any), centers view.
1. **Load Session** (Visible if `has_session` is true):
   - *Action ID*: `LOAD_SESSION|<filename>`
   - *Behavior*: Loads map + saved token positions from the session file.
1. **Calibrate Scale**:
   - *Action ID*: `CALIBRATE_MAP|<filename>`
   - *Behavior*: Loads map and immediately enters "Calibration Mode".
1. **Forget Map**:
   - *Action ID*: `FORGET_MAP|<filename>`
   - *Behavior*: Manually removes the map from the registry and refreshes the menu.

### 4. Session Management

- **Manual Saving Only**:
  - Session state (token positions) is **not** auto-saved when switching maps or exiting.
  - User must explicitly select "Scan & Save" to persist the current state.
- **File Naming**:
  - Session files are stored in `sessions/` directory.
  - Filename format: `<map_filename_stem>_<hash_of_full_path>.json` to uniquely link to the map file even if filenames are similar in different folders.

### 5. Interaction Flow

1. **User**: Runs `python hand_tracker.py --maps "my_campaign/maps/*.svg"`
1. **System**: `MapConfigManager` expands glob, updates `map_state.json`, pruning missing maps.
1. **User**: Selects "Maps" -> "Dungeon Level 1 (!)".
1. **System**: Shows Action Menu for "Dungeon Level 1".
1. **User**: Selects "Calibrate Scale".
1. **System**: `InteractiveApp` parses `CALIBRATE_MAP|...`, loads map, enters Calibration Mode. User sets 1-inch grid.
1. **System**: Saves grid config. Updates Map List status (removes `(!)`).
1. **User**: Places tokens, plays.
1. **User**: Selects "Session" -> "Save".
1. **System**: Saves token positions to `sessions/dungeon_level_1_....json`. Updates Map List status (adds `(*)`).

## Interfaces

### `MapConfigManager` (Additions)

```python
class MapConfigManager:
    # ... existing methods ...

    def scan_for_maps(self, patterns: List[str]) -> List[str]:
        """
        Expands globs in patterns, checks for existence, 
        adds new maps to config, and removes missing maps.
        Returns the updated list of known map filenames.
        """
        pass

    def get_map_status(self, filename: str) -> Dict[str, bool]:
        """
        Returns {'calibrated': bool, 'has_session': bool}
        """
        pass
        
    def forget_map(self, filename: str):
        """Removes map from config."""
        pass
```

### `MenuSystem` (Changes)

The `MenuSystem` needs to handle the dynamic injection.

- **Option A**: Pass a `menu_generator` callback to `InteractiveApp`.
- **Option B**: Expose a method `update_root_menu(new_root: MenuItem)`.

We will choose **Option B**. `InteractiveApp` will reconstruct the entire `ROOT_MENU` when the map list changes and call `menu_system.set_root_menu(new_root)`.

## Implementation Tasks

- [x] **Phase 1: CLI & Configuration**
  - [x] Update `argparse` to support `--maps` (list of strings).
  - [x] Implement `MapConfigManager.scan_for_maps` using `glob`.
  - [x] Implement `MapConfigManager.forget_map`.
  - [x] Update `MapEntry` to track `last_seen`.
- [x] **Phase 2: Session Backend**
  - [x] Refactor `SessionManager` to save files linked to specific maps (hashing path).
  - [x] Implement `MapConfigManager.get_map_status` (checks for session file existence).
- [x] **Phase 3: Menu UI Construction**
  - [x] Create `src/light_map/menu_builder.py`.
  - [x] Implement `build_map_submenu(map_config: MapConfigManager) -> MenuItem`.
  - [x] Implement `build_root_menu(map_config: MapConfigManager) -> MenuItem` which combines static items with the dynamic map list.
  - [x] Update `MenuSystem` to allow replacing the root menu via `set_root_menu`.
- [x] **Phase 4: Integration**
  - [x] Update `InteractiveApp` to initialization:
    - [x] Parse `--maps`.
    - [x] Call `scan_for_maps`.
    - [x] Build initial menu.
  - [x] Update `InteractiveApp._process_menu_mode` to handle:
    - [x] `LOAD_MAP|...`
    - [x] `LOAD_SESSION|...`
    - [x] `CALIBRATE_MAP|...`
    - [x] `FORGET_MAP|...`
    - [x] `SCAN_FOR_MAPS` (Triggers rescan and menu rebuild).

## Testing Strategy

### Unit Tests

- **`test_map_config_scanning.py`**:
  - Mock `glob.glob` and `os.path.exists`.
  - Verify `scan_for_maps` adds new files and removes missing ones.
  - Verify `scan_for_maps` handles duplicates and invalid extensions.
- **`test_menu_builder.py`**:
  - Mock `MapConfigManager` with a set of known maps (some calibrated, some with sessions).
  - Verify `build_map_submenu` creates the correct hierarchy.
  - Verify `action_id` strings are formatted correctly (e.g. `LOAD_MAP|/tmp/map.svg`).
  - Verify sorting is alphabetical.
- **`test_session_manager.py`**:
  - Verify that different paths produce different session filenames.
  - Verify that the same path always produces the same session filename.

### Integration Tests

- **`test_integration_map_loading.py`**:
  - Instantiate `InteractiveApp`.
  - Simulate triggering `LOAD_MAP|test_map.svg`.
  - Assert that `app.svg_loader` is loaded with the correct file.
  - Assert that `app.mode` changes (if applicable).

## Migration

- Existing `map_state.json` entries will be preserved.
- `--map` argument will be deprecated but aliased to `--maps` for backward compatibility.
