# Refactor Blockers to Static Typing Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate visibility blockers from raw dictionaries to statically typed dataclass objects throughout the backend while maintaining frontend compatibility.

**Architecture:** Use the existing `VisibilityBlocker` dataclass in `WorldState`. Update all systems (SVG Loading, Visibility Engine, Interaction, Rendering) to use this dataclass with a consistent `points` attribute. Handle dictionary serialization only at the `WorldState.to_dict()` boundary for the frontend.

**Tech Stack:** Python (Dataclasses, TypedDict), OpenCV, svgelements.

---

### Task 1: Fix InteractiveApp sync logic

**Files:**
- Modify: `src/light_map/interactive_app.py`

**Step 1: Implement correct _sync_blockers_to_state signature**
Ensure it accepts an optional `state` and uses `list()` for versioning.

```python
    def _sync_blockers_to_state(self, state: Optional["WorldState"] = None):
        """Synchronizes visibility engine blockers to the public state."""
        # Use list() to create a NEW instance, ensuring VersionedAtom detects the change
        # even if we mutated the blockers in-place.
        blockers = list(self.visibility_engine.blockers)
        self.state.blockers = blockers
        if state is not None and state is not self.state:
            state.blockers = blockers

        # Ensure visibility mask is updated to trigger re-render if blockers changed
        if self.state.visibility_mask is not None:
            self.state.visibility_mask = self.state.visibility_mask.copy()
        if (
            state is not None
            and state is not self.state
            and state.visibility_mask is not None
        ):
            state.visibility_mask = state.visibility_mask.copy()
```

**Step 2: Fix load_map call site**
Remove the incorrect `state` argument in `load_map`.

```python
                # Sync state.blockers so frontend gets updated is_open status
                self._sync_blockers_to_state()
```

**Step 3: Verify with Door Restoration Test**
Run: `pytest tests/test_door_state_restoration.py::test_door_state_restoration_syncs_to_state -v`
Expected: PASS (if Task 2 is also done or if we fix the dispatcher)

### Task 2: Fix ActionDispatcher toggle logic

**Files:**
- Modify: `src/light_map/action_dispatcher.py`

**Step 1: Update handle_toggle_door to use dot-notation and pass state**

```python
        for blocker in app.visibility_engine.blockers:
            if blocker.id == door_id:
                blocker.is_open = not blocker.is_open
                found = True
        if found:
            app.visibility_engine.update_blockers(
                app.visibility_engine.blockers,
                app.fow_manager.width,
                app.fow_manager.height,
            )
            app._sync_blockers_to_state(state)
```

**Step 2: Run Toggle Door Test**
Run: `pytest tests/test_door_state_restoration.py::test_toggle_door_syncs_to_state -v`
Expected: PASS

### Task 3: Bulk Update Tests to use points and dot-notation

**Files:**
- Modify: `tests/**/*.py` (especially `test_token_movement.py`, `test_svg_loader_visibility.py`, `test_visibility_logic.py`, `test_visibility_starfinder.py`)

**Step 1: Replace segments with points in all tests**
Run: `find tests -name "*.py" -exec sed -i 's/\bsegments\b/points/g' {} +`

**Step 2: Fix any remaining dictionary access in tests**
Manually or via regex fix `blocker["id"]` -> `blocker.id`, etc.

**Step 3: Run all core visibility tests**
Run: `pytest tests/test_door_layer.py tests/test_door_state_restoration.py tests/test_svg_loader_visibility.py tests/test_visibility_logic.py -v`
Expected: ALL PASS

### Task 4: Final Verification and Cleanup

**Step 1: Check for any remaining raw string key access**
Run: `grep -r "blocker.get(" src/` and `grep -r "blocker\[" src/`
Expected: NO MATCHES (except in `to_dict` serialization if any)

**Step 2: Run full project test suite**
Run: `pytest -v`
Expected: ALL PASS (related to blockers)
