# Tactical Testing Framework (Golden-Master)

## 1. Goal
Provide a deterministic, high-fidelity testing environment for verifying the Tactical Cover and "Cone of Fire" features. This framework enables automated regression testing of complex geometric scenarios, ensuring that visual feedback (cones) and mathematical logic (AC/Reflex bonuses) remain aligned and correct as the engine evolves.

## 2. Core Concepts

### 2.1 Golden-Master (Characterization) Testing
Instead of manually asserting complex geometric arrays, the framework uses "Golden-Master" testing. Each test run generates a high-resolution snapshot of the tactical state (JSON) and a visual representation (PNG). New results are compared against "blessed" golden versions; any deviation triggers a failure, forcing the developer to either fix a regression or "bless" the new behavior.

### 2.2 Grid Normalization
To simplify scenario creation, the framework operates on a normalized **20-cell grid**.
- **Square Maps**: The largest dimension (Width or Height) of the input SVG is automatically scaled to represent 20 grid cells.
- **Coordination**: All coordinates in the YAML configuration are integers corresponding to this 20-cell span, making it easy to reason about token placement and obstacle proximity.

### 2.3 Visual & Mathematical Parity
For every test case, the framework outputs:
- **`{case}.json`**: Contains raw numerical data (AC/Reflex bonuses, `total_ratio`, `best_apex` in SVG units, and discrete `WedgeSegment` indices).
- **`{case}.png`**: A high-resolution (`128px` per cell) render using the actual application `Renderer` and `TacticalOverlayLayer` code. This allows for human verification of textures, outlines, and "pinching" logic.

## 3. Technical Specifications

### 3.1 Test Components
- **Input YAML**: Defines the grid type, token positions, and sizes.
- **Input SVG**: An Inkscape-compatible SVG containing standard layers for geometry:
    - `walls` (MASK_VALUE_WALL = 255)
    - `closed doors` (MASK_VALUE_DOOR_CLOSED = 200)
    - `tall objects` (MASK_VALUE_TALL = 100)
    - `low objects` (MASK_VALUE_LOW = 50)
- **Runner (`scripts/run_tactical_tests.py`)**: The orchestrator that scales the SVG, rasterizes the blocker mask, runs the `VisibilityEngine`, and generates output artifacts.
- **Bless Script (`scripts/bless_tactical_tests.py`)**: Copies current results to the `golden/` directory to update the ground truth.

### 3.2 Automation & CI/CD
The framework is integrated into `pytest` via `tests/test_tactical_golden.py`. This wrapper discovers all `.yaml` files in the `tests/tactical_cases/` directory and executes the runner as a subprocess, failing the test suite if any JSON mismatch is detected.

## 4. Developer Workflow

### 4.1 Creating a New Scenario
1.  Draw a map in Inkscape, using group labels like `walls` or `low objects`. Save as `tests/tactical_cases/my_case.svg`.
2.  Define the tokens in `tests/tactical_cases/my_case.yaml` (e.g., Attacker at `[2, 10]`, Target at `[18, 10]`).
3.  Run the tests: `pytest tests/test_tactical_golden.py`.
4.  The test will fail because no golden file exists.
5.  Inspect `tests/tactical_cases/results/my_case.png` to ensure the cone looks correct.
6.  Inspect `tests/tactical_cases/results/my_case.json` to verify the AC bonuses match Starfinder 1e rules.
7.  Bless the result: `python3 scripts/bless_tactical_tests.py my_case`.

### 4.2 Handling Failures
If a test fails:
1.  Check the diff provided in the output.
2.  Compare `results/{case}.png` against the expected behavior.
3.  If the change was intentional (e.g., an algorithm improvement), run the bless script.
4.  If the change was accidental, fix the regression in `src/light_map/visibility/`.

## 5. Success Criteria
- **Fidelity**: The generated PNG matches the behavior seen on the physical table.
- **Determinism**: Identical SVGs and YAMLs always produce identical JSON outputs.
- **Efficiency**: Running the entire tactical test suite takes less than 5 seconds.
- **Clarity**: JSON statuses use readable strings (`CLEAR`, `OBSCURED_LOW`, `BLOCKED`) rather than internal integers.
