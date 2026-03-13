# Light Map

Light Map is an interactive Augmented Reality (AR) tabletop platform that merges physical gaming with digital enhancements. By turning any flat surface into an interactive display that "understands" the physical objects and hands placed upon it, the system provides a low-cost, high-immersion alternative to traditional digital tabletops.

## Features

- **Projector-Camera Calibration**: Precise mapping between the camera and projector space.
- **Hand Tracking & Gestures**: Interactive control using hand gestures.
- **Dynamic Map System**: Support for SVG and image maps with pan, zoom, and rotation.
- **Token Tracking**: Detects physical tokens and saves/restores session state.
- **Hierarchical Menu**: Hands-free control system.
- **Web Dashboard**: Real-time monitoring and configuration via a browser-based interface.

## Documentation

- [Calibration Guide](docs/calibration.md)
- [Hand Tracking & Gestures](docs/hand_tracking.md)
- [Map System](docs/map_system.md)
- [Menu System](docs/menu_system.md)
- [Token Tracking](docs/token_tracking.md)
- [Remote Application Driver & Web Dashboard](docs/remote_driver.md)

## Installation

### Prerequisites

- **Python 3.12+**
- **Node.js 20+** (for the web dashboard)
- A webcam and a projector

### Backend Setup

1. **Clone the repository and enter the directory**:

   ```bash
   git clone https://github.com/rchandia/light_map.git
   cd light_map
   ```

1. **Create and activate a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

1. **Install the package in editable mode**:
   This registers the `light_map` package and provides the `light-map` command.

   ```bash
   pip install -e .
   ```

### Frontend Setup (Dashboard)

The frontend is a Vite/React application that provides a real-time dashboard and control interface.

1. **Navigate to the frontend directory**:

   ```bash
   cd frontend
   ```

1. **Install dependencies**:

   ```bash
   npm install
   ```

1. **Build the dashboard**:
   This generates the production assets in `frontend/dist`. The backend automatically serves these files when the remote driver is enabled.

   ```bash
   npm run build
   ```

1. **Return to the root directory**:

   ```bash
   cd ..
   ```

______________________________________________________________________

## Running the Application

Once installed, you can use the `light-map` command directly or use the `python -m` syntax.

### 1. Calibration (Initial Setup Only)

1. **Calibrate Camera**:

   ```bash
   python scripts/calibrate.py
   ```

1. **Calibrate Projector**:

   ```bash
   python scripts/projector_calibration.py
   ```

### 2. Standard Execution

To run the application with a specific set of maps:

```bash
light-map --maps "maps/*.svg"
```

*Alternatively:* `python -m light_map --maps "maps/*.svg"`

### 3. Running with the Web Dashboard

To enable the web dashboard (Remote Driver), you must specify a remote input mode for hands or tokens (default is `ignore`).

#### Production Mode (Recommended)

If you have built the frontend using `npm run build`, the dashboard will be served automatically on port `8000` when the remote driver is enabled.

1. Run the app with remote inputs enabled:

   ```bash
   light-map --maps "maps/*.svg" --remote-hands merge
   ```

   *(Modes: `merge` to use both physical and remote inputs, `exclusive` for remote-only, `ignore` to disable)*

1. Open your browser to `http://localhost:8000`

#### Development Mode (Real-time updates)

For frontend development, run the backend and the Vite development server simultaneously.

1. Start the backend with remote driver enabled:
   ```bash
   light-map --maps "maps/*.svg" --remote-hands merge
   ```
1. In a separate terminal, start the frontend development server:
   ```bash
   cd frontend
   npm run dev
   ```
1. Open the development server URL (usually `http://localhost:5173`).

______________________________________________________________________

## Standalone Installation

For a more permanent installation, you can build a standalone executable:

```bash
python scripts/install_app.py
```

This will create a `light-map` binary in `dist/`, install it to `~/.local/bin`, and create a desktop entry.

## Development

- **Tests**: Run `pytest` to execute the test suite.
- **Linting**: Run `ruff check .` to ensure code quality.
