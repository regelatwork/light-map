# Implementation Plan: Full Typed Config Migration

This plan covers the remaining migration of `tokens.json` and `sessions/*.json` files to the Typed Config Synchronization system.

## Phase 1: Schema Expansion

1. **Define Token & ArUco Schemas**:
   - In `src/light_map/core/config_schema.py`, add:
     - `SizeProfileSchema(BaseModel)`
     - `ArucoDefinitionSchema(BaseModel)`
     - `TokenConfigSchema(BaseModel)`: To represent the structure of `tokens.json`.
1. **Define Session & Map Schemas**:
   - In `src/light_map/core/config_schema.py`, add:
     - `ViewportStateSchema(BaseModel)`
     - `TokenSchema(BaseModel)`
     - `SessionDataSchema(BaseModel)`: To represent session files.
     - `MapEntrySchema(BaseModel)`: To represent entries in `map_state.json`.

## Phase 2: Backend Refactor (Migration)

1. **Migrate `MapConfigManager` (tokens.json)**:
   - Use `TokenConfigSchema` in `_load` and `_save`.
   - Update `aruco_defaults` to use numeric keys consistently (handling the string-to-int conversion during Pydantic validation).
1. **Migrate `SessionManager` (sessions/\*.json)**:
   - Use `SessionDataSchema` to replace the manual dictionary parsing in `load_session` and `save_session`.
   - Leverage `sync_pydantic_to_dataclass` for recursive synchronization of `ViewportState` and `Token` lists.

## Phase 3: Frontend Synchronization

1. **Update `generate_ts_schema.py`**:
   - Add the new schemas (`TokenConfigSchema`, `SessionDataSchema`, etc.) to the generation loop.
   - Ensure the generator handles nested models and `List[BaseModel]` correctly.
1. **Update Frontend Types**:
   - Replace manual interfaces in `frontend/src/types/system.ts` and `frontend/src/types/tokens.ts` with the generated versions.

## Phase 4: Validation & Cleanup

1. **Nested Object Tests**:
   - Add tests to `tests/test_config_sync.py` verifying that a change in a nested Pydantic model (e.g., `viewport.zoom`) correctly propagates to the runtime dataclass.
1. **Dictionary Key Tests**:
   - Verify that `aruco_defaults` keys are correctly handled as numbers in the schema and strings in the JSON storage.
1. **Regression Testing**:
   - Run `tests/test_e2e_playback.py` and `tests/test_map_loading_regressions.py` to ensure map and session loading remains intact.

## Technical Details

### Dict Key Handling

The Pydantic schema for `tokens.json` should use `Dict[int, ArucoDefinitionSchema]`. The generator script will map this to `Record<number, ArucoDefinition>`.

### Recursive Sync

Ensure `sync_pydantic_to_dataclass` handles `List[BaseModel]` by mapping them to `List[Dataclass]`.

### Example: MapEntrySchema

```python
class MapEntrySchema(BaseModel):
    scale_factor: float = 1.0
    viewport: ViewportStateSchema = Field(default_factory=ViewportStateSchema)
    grid_spacing_svg: float = 0.0
    aruco_overrides: Dict[int, ArucoDefinitionSchema] = Field(default_factory=dict)
```
