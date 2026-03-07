# Light Map

Light Map is an interactive Augmented Reality (AR) tabletop platform that merges physical gaming with digital enhancements. By turning any flat surface into an interactive display that "understands" the physical objects and hands placed upon it, the system provides a low-cost, high-immersion alternative to traditional digital tabletops.

## Features

- **Projector-Camera Calibration**: Precise mapping between the camera and projector space.
- **Hand Tracking & Gestures**: Interactive control using hand gestures.
- **Dynamic Map System**: Support for SVG and image maps with pan, zoom, and rotation.
- **Token Tracking**: Detects physical tokens and saves/restores session state.
- **Hierarchical Menu**: Hands-free control system.

## Documentation

- [Calibration Guide](docs/calibration.md)
- [Hand Tracking & Gestures](docs/hand_tracking.md)
- [Map System](docs/map_system.md)
- [Menu System](docs/menu_system.md)
- [Token Tracking](docs/token_tracking.md)
- [Remote Application Driver (WebDriver)](docs/remote_driver.md)

## Quick Start

### Prerequisites

- Python 3.12+
- A webcam and a projector

### Installation

1.  **Clone the repository and enter the directory**:
    ```bash
    git clone https://github.com/rchandia/light_map.git
    cd light_map
    ```

1.  **Create and activate a virtual environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

1.  **Install the package in editable mode**:
    This registers the `light_map` package and provides the `light-map` command.
    ```bash
    pip install -e .
    ```

### Running the Application

Once installed, you can use the `light-map` command directly or use the `python -m` syntax.

1.  **Calibrate Camera**:
    ```bash
    python scripts/calibrate.py
    ```

1.  **Calibrate Projector**:
    ```bash
    python scripts/projector_calibration.py
    ```

1.  **Run the App**:
    ```bash
    light-map --maps "maps/*.svg"
    ```
    *Alternatively:* `python -m light_map --maps "maps/*.svg"`

   See [Map System](docs/map_system.md) for more details on loading maps.

## Development

- **Tests**: Run `pytest` to execute the test suite.
- **Linting**: Run `ruff check .` to ensure code quality.
