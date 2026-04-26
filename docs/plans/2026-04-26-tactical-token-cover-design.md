# Tactical Token Cover (Soft Cover) Implementation Plan

## Objective
Implement dynamic tactical cover provided by tokens ("Soft Cover") to accurately calculate Starfinder 1e cover bonuses when creatures (allies or enemies) stand between an attacker and their target.

## Background & Motivation
Currently, the system only calculates cover from static map features (walls, doors, low objects). In Starfinder 1e, creatures provide "Soft Cover" to targets of the same size or smaller. Soft cover grants a **+4 AC bonus** but importantly provides **no bonus to Reflex saves**.

## Proposed Solution: "Stamp & Trace"
We will implement an efficient "Stamp & Trace" approach to minimize performance overhead during tactical calculations:
1.  **Mask Augmentation:** Before calculating cover for an inspected token, we will copy the static `blocker_mask`.
2.  **Token Stamping:** We will stamp the footprints of all active tokens (excluding the attacker and target) onto this temporary mask using a new constant `MASK_VALUE_SOFT_COVER = 75`.
3.  **Trace Update:** The Numba ray-tracing function will be updated to recognize this new value and return a distinct "Soft Cover" status, allowing the engine to calculate AC and Reflex bonuses independently.

## Key Files & Context
-   `src/light_map/visibility/visibility_engine.py`: Numba tracing and cover calculation logic.
-   `src/light_map/visibility/exclusive_vision_scene.py`: Orchestrates the tactical calculations and supplies the token list.
-   `features/tactical_cover_and_reflex.md`: Documentation to be updated with the new Soft Cover rules.
-   `tests/tactical_cases/`: Directory for the new golden tests.

## Implementation Steps
1.  **Engine Constants & Logic (`visibility_engine.py`)**
    *   Add `MASK_VALUE_SOFT_COVER = 75`.
    *   Update `_numba_trace_path` to detect `75` and return a new status `3` (Soft Cover). Ensure that Hard Cover (Walls/Tall objects) overrides Soft Cover if encountered later in the trace.
    *   Modify `_numba_calculate_cover_grade` to track `soft_cover_count` alongside `wall_count`.
    *   Update `calculate_token_cover_bonuses` to grant +4 AC for Soft Cover but +0 Reflex, while preserving Hard Cover bonuses if applicable.

2.  **Scene Integration (`exclusive_vision_scene.py`)**
    *   Extract footprint generation logic (e.g., caching footprints by token size).
    *   Create a temporary `blocker_mask` copy.
    *   Iterate through `all_tokens` and stamp their footprints onto the mask if they are not the `source_token` or `target_token`.
    *   Pass the augmented mask to `calculate_token_cover_bonuses`.

3.  **Documentation Update (`features/tactical_cover_and_reflex.md`)**
    *   Add a new section for "Soft Cover (Creatures)".
    *   Document the rules: +4 AC, +0 Reflex, mutual exclusion for shared spaces.

4.  **Golden Tests & Validation (`tests/tactical_cases/`)**
    *   Create `soft_cover_basic.yaml`: A token providing cover between attacker and target.
    *   Create `soft_cover_override.yaml`: A token and a wall between attacker and target (wall Reflex bonus should apply).
    *   Create `soft_cover_clear.yaml`: A token nearby but not blocking the line of effect.
    *   Run `scripts/bless_tactical_tests.py` to generate the golden JSON/PNG files.

## Verification & Testing
-   Run unit tests: `pytest tests/ -k "cover"`
-   Verify golden tests: `python scripts/run_tactical_tests.py`
-   Ensure performance remains stable during Exclusive Vision with multiple tokens present.
