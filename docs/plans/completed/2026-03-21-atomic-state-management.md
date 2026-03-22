# Atomic Versioned State & Temporal Management Implementation Plan

**Goal:** Transition the monolithic `WorldState` to a decentralized, Atomic State architecture with a centralized `TemporalEventManager`.

**Architecture:** Replace manual timestamp management with `VersionedAtom` objects that automatically track changes using monotonic timestamps. `WorldState` becomes a registry of these atoms, and `TemporalEventManager` becomes the sole authority for time-based state updates.

______________________________________________________________________

## Phase 1: Core Foundation (COMPLETED)

- [x] **Task 1: Implement `VersionedAtom`**: Created `src/light_map/core/versioned_atom.py` with monotonic nanosecond timestamps and equality logic.
- [x] **Task 2: Transaction Support**: Added `Transaction` class and `@contextmanager transaction()` to `WorldState`.
- [x] **Task 3: Initial Migration**: Migrated `viewport`, `tokens`, `blockers`, and `menu_state` to atoms.
- [x] **Task 4: Temporal Authority Infrastructure**: Added `advance()` to `TemporalEventManager` to update `system_time_atom`.

______________________________________________________________________

## Phase 2: Temporal Integration & UI Atomicity (COMPLETED)

- [x] **Task 1: Activate Temporal Authority**: Call `self.events.advance(dt)` inside `InteractiveApp.process_state`.
- [x] **Task 2: Atomic UI Feedback States**: Convert `dwell_state` and `summon_progress` to `VersionedAtom` objects.
- [x] **Task 3: Declarative State Mutations**: Implement `TemporalEventManager.schedule_mutation(atom, new_value, delay)`.

______________________________________________________________________

## Phase 3: Deep Atomic Migration (COMPLETED)

- [x] **Task 4: Atomic Selection & Grid Metadata**: Move `SelectionState` and `GridMetadata` to `VersionedAtom` objects.
- [x] **Task 5: Layer Dependency Audit**: Audit and update `get_current_version()` for all layers to aggregate all atom dependencies.

______________________________________________________________________

## Phase 4: Enforcement & Cleanup (COMPLETED)

- [x] **Task 6: Eliminate Manual Versioning**: Removed all manual version increments and redundant setters in `WorldState`.
- [x] **Task 7: Transactional Detection Results**: Wrapped `WorldState.apply()` in `transaction()` for atomic snapshots.
- [x] **Task 8: API Unification**: Standardized public API to use `_version` naming across the codebase.
- [x] **Task 9: Visibility Logic Refactor**: Moved visibility aggregation into a dedicated `_visibility_aggregate_version_atom`.
