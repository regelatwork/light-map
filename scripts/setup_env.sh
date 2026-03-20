#!/bin/bash
set -e

# Configuration
PYTHON_VERSION=$(cat .python-version 2>/dev/null || echo "3.12.9")
VENV_DIR=".venv"
OPENCV_VER="4.11.0" # Current stable 4.x

echo "===================================================="
echo "Starting Light Map environment setup..."
echo "===================================================="

# 0. Check for system dependencies
echo "Checking for system dependencies..."
DEPS=(cmake gcc g++ pkg-config libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgtk-3-dev)
MISSING_DEPS=()

for dep in "${DEPS[@]}"; do
    if ! dpkg -s "$dep" >/dev/null 2>&1; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Error: Missing system dependencies: ${MISSING_DEPS[*]}"
    echo "Please install them using:"
    echo "sudo apt-get update && sudo apt-get install -y ${MISSING_DEPS[*]}"
    exit 1
fi
echo "System dependencies satisfied."

# 1. Check for pyenv
if ! command -v pyenv &> /dev/null; then
    echo "Error: pyenv is not installed. Please install it first."
    exit 1
fi

# Set local pyenv root if it exists to avoid permission issues
if [ -d "$HOME/.pyenv" ]; then
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"
fi

# 2. Install/Check Python version
echo "Checking for Python ${PYTHON_VERSION}..."
if ! pyenv versions --bare | grep -qx "${PYTHON_VERSION}"; then
    echo "Installing Python ${PYTHON_VERSION} via pyenv..."
    pyenv install "${PYTHON_VERSION}"
else
    echo "Python ${PYTHON_VERSION} is already installed."
fi

# 3. Create virtual environment
echo "Creating/Updating virtual environment in ${VENV_DIR}..."
PYENV_PYTHON_BIN=$(pyenv prefix "${PYTHON_VERSION}")/bin/python

if [ ! -d "${VENV_DIR}" ]; then
    "${PYENV_PYTHON_BIN}" -m venv "${VENV_DIR}"
else
    echo "Virtual environment already exists."
fi

# 4. Activate venv and upgrade base tools
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip setuptools wheel

# 5. Build and install custom OpenCV
echo "Building OpenCV ${OPENCV_VER} with GStreamer support..."
echo "NOTE: This step can take 15-30 minutes depending on your CPU."

# Check if OpenCV with GStreamer is already installed correctly
if python -c "import cv2; print(cv2.getBuildInformation())" | grep -q "GStreamer:.*YES"; then
    echo "OpenCV with GStreamer support already detected. Skipping build."
else
    TMPDIR=$(mktemp -d)
    echo "Using temporary directory: ${TMPDIR}"
    cd "${TMPDIR}"

    echo "Cloning opencv-python repository..."
    git clone --branch ${OPENCV_VER} --depth 1 --recurse-submodules --shallow-submodules https://github.com/opencv/opencv-python.git opencv-python-build
    cd opencv-python-build

    # Configuration for the build
    export ENABLE_CONTRIB=1
    export ENABLE_HEADLESS=0
    export CMAKE_ARGS="-DWITH_GSTREAMER=ON -DWITH_GTK=ON -DBUILD_EXAMPLES=OFF"

    echo "Running pip wheel (this will take a while)..."
    python -m pip wheel . --verbose

    WHEEL_FILE=$(ls opencv_contrib_python*.whl | head -n 1)
    if [ -f "$WHEEL_FILE" ]; then
        echo "Installing custom OpenCV wheel: $WHEEL_FILE"
        pip install --force-reinstall "$WHEEL_FILE"
    else
        echo "Error: Build failed, no wheel found."
        exit 1
    fi

    cd - > /dev/null
    rm -rf "${TMPDIR}"
fi

# 6. Install MediaPipe and other requirements
echo "Installing MediaPipe and other requirements..."
# mediapipe expects opencv-contrib-python, which we just built.
pip install mediapipe

# Now install the rest of the project requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Finally, install the project in editable mode
pip install -e .

echo "===================================================="
echo "Setup complete! Activate your environment with:"
echo "source ${VENV_DIR}/bin/activate"
echo "===================================================="
