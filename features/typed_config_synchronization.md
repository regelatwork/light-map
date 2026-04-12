# Typed Config Synchronization

## Overview

Typed Config Synchronization is a system designed to eliminate manual duplication and "configuration drift" between the Python backend and the React frontend. It ensures that every configuration setting is defined exactly once in a **Single Source of Truth** (SSOT) and is consistently represented in storage, runtime state, API validation, and the user interface.

## Architecture

### 1. Single Source of Truth (SSOT)

All configuration fields, default values, and user-facing metadata (labels, descriptions, constraints) are defined using **Pydantic `BaseModel`s**. Each configuration storage file (e.g., `map_state.json`, `tokens.json`) has a corresponding Pydantic schema.

### 2. Static Type Safety & Generation

To bridge the language gap, a generator script (`scripts/generate_ts_schema.py`) inspects the Pydantic models and produces:

- **TypeScript Interfaces**: Mirror the Pydantic models exactly.
- **Metadata Registry**: A typed object containing labels, descriptions, and numeric constraints (`min`, `max`, `step`).

**Invariant:** The frontend build *must* fail if the backend schema changes and the generator script has not been run or the frontend code has not been updated to match.

### 3. Generic Backend Synchronization

Instead of manual field-by-field updates, the system uses generic utilities:

- **Validation**: Incoming API payloads are validated against the Pydantic schema, providing automatic typecasting and range checking.
- **State Sync**: A utility function `sync_pydantic_to_dataclass` synchronizes values from a validated Pydantic instance to the runtime application state objects (dataclasses). This utility:
  - Performs **recursive synchronization** for nested models (e.g., `ViewportState` within `MapEntry`).
  - Handles **type conversion** between Pydantic-validated types and legacy dataclass fields.
  - Manages **Enum mapping** (e.g., Python `StrEnum` to the specific runtime enum instances).

### 4. Storage to Runtime Propagation

When a configuration update is received via the API:

1. The `MapConfigManager` validates the update and saves it to the on-disk storage file.
1. The manager then triggers a sync to the global `AppConfig` instance (the runtime state).
1. The application components (e.g., `InputProcessor`, `ArucoDetector`) observe the `AppConfig` for changes, ensuring zero-latency updates without a restart.

### 5. Metadata-Driven UI

The frontend uses generic React components (e.g., `<ConfigNumberInput />`) that are typed against the generated interfaces. These components:

- Look up their own labels and tooltips from the metadata registry using a static key.
- Inherit constraints like `min`, `max`, and `step` directly from the backend `Field` definitions.
- Correctiy handle **Complex Types** like `Optional` values (mapping to `null | undefined` in TS) and dictionaries with numeric keys (mapping to `Record<number, T>`).

### 6. Synchronization Verification (Python Tests)

To prevent developers from forgetting to run the generation script, a dedicated Python test will:

1. Generate the TypeScript schema content in-memory from the current Pydantic models.
1. Compare it to the existing `frontend/src/types/schema.generated.ts` file on disk.
1. **Fail with a loud, clear message** if they differ:
   `"ERROR: Configuration schema is out of sync. Please run 'python3 scripts/generate_ts_schema.py' to update the frontend types."`

This ensures that the CI/CD pipeline and local `pytest` runs will catch synchronization issues immediately.

## Workflow Invariants

1. **Schema-First**: All new configuration settings must be added to a Pydantic model in `src/light_map/core/config_schema.py` (or similar).
1. **Mandatory Generation**: After any change to a Pydantic model, `scripts/generate_ts_schema.py` **must** be executed to synchronize the frontend types.
1. **No String Keys**: The frontend must use statically-checked keys (`keyof T`) to reference configuration fields, preventing runtime "missing field" errors.
1. **Zero-Manual-API**: Adding a field to the schema automatically makes it available for updates via the generic API update handler without requiring code changes in the action dispatcher.
