# Design: Atomic Versioned State & Temporal Management

## 1. Overview

The current state management in Light Map relies on a monolithic `WorldState` and manual timestamp increments (`increment_X_timestamp`). This architecture is prone to "masked updates" (where small increments are ignored by large timestamps) and "hidden state" (logic that triggers re-renders without observable state changes).

This design proposes a decentralized, **Atomic State** architecture where `WorldState` acts as a registry for modular **Versioned Atoms**. Furthermore, it centralizes all time-based logic into an evolved **Temporal Event Manager**, making time an explicit, observable part of the system state.

______________________________________________________________________

## 2. Core Principles

1. **Observability**: Rendering is a pure function of the `WorldState`. No re-render occurs without an atom changing its version.
1. **Encapsulation**: Each piece of state ("Atom") manages its own data, equality logic, and version timestamp.
1. **Temporal Authority**: The `TemporalEventManager` is the sole modifier of time-dependent state atoms (clocks, timeouts, animations).
1. **Monotonicity**: All versions use nanosecond-scale monotonic timestamps to ensure global compatibility with `max()` comparisons.

______________________________________________________________________

## 3. Versioned State Atoms

Instead of raw attributes, `WorldState` hosts `VersionedAtom` objects. An atom encapsulates the "when" and the "what".

### Interface

```python
class VersionedAtom(Generic[T]):
    def __init__(self, initial_value: T, name: str, equality_fn: Optional[Callable] = None):
        self._value = initial_value
        self._timestamp = time.monotonic_ns()
        self._name = name
        self._equality_fn = equality_fn or (lambda a, b: a == b)

    @property
    def value(self) -> T:
        return self._value

    @property
    def timestamp(self) -> int:
        """The logical version of this data."""
        return self._timestamp

    def update(self, new_value: T) -> bool:
        """
        Updates the data. 
        Returns True and refreshes timestamp ONLY if the change is meaningful.
        """
        if not self._equality_fn(self._value, new_value):
            self._value = new_value
            self._timestamp = time.monotonic_ns()
            return True
        return False
```

______________________________________________________________________

## 4. WorldState: The State Registry

`WorldState` transitions from a data repository to a **State Host**. It no longer contains logic for comparing tokens or landmarks; it simply exposes the atoms.

### Structure

```python
class WorldState:
    def __init__(self):
        # Atoms
        self.viewport = VersionedAtom(ViewportState(), "viewport")
        self.tokens = VersionedAtom([], "tokens", equality_fn=self._tokens_equal)
        self.blockers = VersionedAtom([], "blockers")
        self.system_time = VersionedAtom(0.0, "system_time") # Managed by Temporal Manager
        self.scene_metadata = VersionedAtom({}, "scene_metadata")
        
        # Aggregate logic
        self.visibility_timestamp = 0 # Computed via max() of relevant atoms
```

______________________________________________________________________

## 5. Batching & Transactional Updates

To ensure that complex operations (like a simultaneous move and zoom) trigger only a single re-render cycle, `WorldState` supports transactional updates.

### Transaction Pattern

```python
with world_state.transaction() as tx:
    tx.update(world_state.viewport, new_viewport)
    tx.update(world_state.menu_state, new_menu_state)
# All updates share the same timestamp and notify listeners once at the end.
```

The transaction captures a single `time.monotonic_ns()` at the start and applies it to all modified atoms, preventing intermediate "partial" states from being rendered.

______________________________________________________________________

## 6. IPC & DetectionResult Integration

Detection results from worker processes (ArUco, Hands, Gestures) must be bridged into the atomic state of the `MainProcess`.

1. **Direct Mapping**: Each detection stream (e.g., `ArucoDetectionResult`) maps to a specific `VersionedAtom` (e.g., `state.tokens`).
1. **Temporal Alignment**: When a `DetectionResult` includes a hardware capture timestamp, that timestamp is used as the atom's version. This ensures that temporal math remains consistent even if IPC delivery is slightly delayed.
1. **Batch Application**: When multiple detections (e.g., hand landmarks and a gesture) arrive in a single IPC bundle, they are applied via a `transaction()` to ensure the renderer sees a consistent snapshot of the physical world.

______________________________________________________________________

## 7. Performance Optimization for Collections

For large collections like `tokens` or `landmarks`, standard deep equality checks can be expensive.

- **Identity Tracking**: Use stable IDs for elements. The `equality_fn` should first check if the set of IDs has changed, then perform shallow comparisons on existing items.
- **Dirty Flags**: For high-frequency data (like hand landmarks), use a distance threshold in the `equality_fn` to avoid updating the version for sub-pixel sensor jitter.
- **Vectorized Comparison**: Where possible, use NumPy-based comparisons for coordinate arrays to keep the main loop latency low.

______________________________________________________________________

## 8. Temporal Event Manager: The Sole Time Authority

The `TemporalEventManager` is upgraded from a callback scheduler to the exclusive owner of temporal state.

### Responsibilities

1. **The Master Clock**: Increments the `state.system_time` atom every loop iteration.
1. **State Mutation Scheduling**: Replaces callbacks with **State Mutations**. Instead of "running code in 2 seconds," it "updates atom X to value Y in 2 seconds."
1. **Recurring Updates**: Manages atoms that must change periodically (e.g., `pulse_animation` atom).
1. **Timeout Management**: Handles expiration of transient state (e.g., removing hands if not seen for 0.5s) by scheduling a "clear" mutation.

### Pattern Shift

- **Old**: `InputCoordinator` checks `current_time - last_seen > 0.5` and manually increments `hands_timestamp`.
- **New**: `InputCoordinator` updates the hand atom. If hands are found, it schedules a mutation in `TemporalEventManager` to clear the hand atom in 0.5s (canceling any previous clear request).

______________________________________________________________________

## 9. Elimination of "Logical" Updates

"Logical" updates are currently used when internal class variables change. In the new design, these variables must be moved into an atom.

| Current "Logical" Need | Atomic Solution |
| :--- | :--- |
| **Animation Frame** | Layer depends on `state.system_time.timestamp`. Re-render happens every tick time changes. |
| **Scene Step Change** | Scene updates `state.scene_metadata.update({"step": 2})`. Timestamp changes automatically. |
| **GM Toggle (FoW)** | Action updates `state.fow_config.update({"enabled": False})`. |
| **Dwell Progress** | Scene updates `state.dwell_progress.update(0.75)` every tick. |

______________________________________________________________________

## 10. Rendering Pipeline

The `Renderer` becomes significantly simpler:

1. **Version Gathering**: For each layer, gather the `timestamp` of every atom it depends on.
1. **Comparison**: `max(dependent_timestamps)`.
1. **Decision**: If the max timestamp is greater than the last rendered version for that layer, re-generate patches.

This ensures that the **Door Layer** only re-renders if:

- `state.viewport` version changes (move/zoom).
- `state.blockers` version changes (door toggled).
- `state.system_time` version changes (if it has animations).

______________________________________________________________________

## 11. Incremental Migration Strategy

To transition from the monolithic `WorldState` without a "Big Bang" refactor, we follow a staged approach:

1. **Phase 1: Simple Atoms**: Migrate isolated states like `viewport`, `menu_state`, and `fow_config`. These have minimal dependencies.
1. **Phase 2: Hybrid WorldState**: `WorldState` will temporarily host both legacy raw attributes and new `VersionedAtom` members.
1. **Phase 3: Collection Migration**: Move complex collections (`tokens`, `blockers`) to atoms once the optimized `equality_fn` patterns are verified.
1. **Phase 4: Full Deprecation**: Remove legacy `increment_X_timestamp` methods and manual timestamp management once all layers depend exclusively on atoms.

______________________________________________________________________

## 12. Benefits

- **Zero Masking**: All versioning uses the same nanosecond scale.
- **No Forgotten Updates**: Updating data *is* updating the version.
- **Testing & Playback**: By capturing the sequence of atom updates, we can perfectly recreate any bug or user session.
- **Decoupling**: Scenes and Managers don't need to know about "timestamps"; they just provide new data to atoms.
