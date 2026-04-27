# Feature: Web-Based Control Interface (Light Map Dashboard)

## 1. Goal

The **Web-Based Control Interface** (Light Map Dashboard) provides a high-level, interactive way to manage the Light Map system. It allows users to monitor real-time state, perform physical calibration through guided wizards, manage map and token assets, and perform spatial adjustments (like grid calibration and door management) through a unified web interface.

## 2. Core Concepts

### 2.1 Single-Page Architecture

The dashboard is a **React** application built for speed and high interactivity. It is served directly by the **Remote Driver** process, ensuring zero-configuration deployment when the system is running.

### 2.2 Dual-Channel Communication

The interface uses two primary methods to communicate with the system:

- **REST API (HTTP)**: For transactional commands like "Open Door", "Load Map", "Save Token Config", or "Upload Asset".
- **Real-Time Stream (WebSockets)**: A bi-directional channel for low-latency state updates (token positions, hand gestures, and system logs), enabling a "live" feel for moving objects on the screen.

### 2.3 Schematic View (Interactive Canvas)

A central SVG-based canvas provides a pixel-perfect spatial representation of the tabletop. It maps standard world coordinates to a zoomable, pannable 2D view, allowing for direct interaction with spatial elements.

## 3. Technical Specifications

### 3.1 Backend Integration (FastAPI)

The existing `Remote Driver` is extended to handle:

- **Static File Serving**: Serves the production-built React application from the `/` route.
- **WebSocket Broadcast**: A `/ws/state` endpoint that pushes the shared `state_mirror` to all connected clients at 30Hz.
- **Asset Management API**: Endpoints for uploading and listing SVG maps, token images, and configuration JSONs.
- **Calibration Bridge**: Wraps existing calibration logic (e.g., chessboard detection, homography calculation) into API-driven steps for the web UI.

### 3.2 Frontend Architecture (React)

- **`useSystemState` Hook**: Manages the WebSocket lifecycle and provides a reactive global state object.
- **SVG Canvas Layers**:
  - **Map Layer**: Background image or SVG representation.
  - **Grid Layer**: Draggable grid lines for visual calibration.
  - **Token Layer**: Real-time representation of detected and simulated tokens.
  - **Tactical Cover Layer**: Visualizes vision wedges (radar) and cover bonuses for selected tokens.
  - **Interaction Layer**: Overlay for UI elements like doors and interactive zones.
- **Configuration Sidebar**: Form-based editing for token properties and system settings with live preview.
- **Control Modules**:
  - **Calibration Wizards**: Step-by-step UI for Intrinsic/Extrinsic and Projector-Camera calibration.
  - **Vision Control**: Toggles for "Exclusive Vision" (projector masking) and "Hand/Token Masking".
  - **Asset Library**: A browser for managing uploaded maps, sessions, and token definitions.

## 4. Implementation Details

- **Tech Stack (Frontend)**: React, Tailwind CSS, Vite.
- **Tech Stack (Backend)**: FastAPI, Uvicorn (WebSocket support).
- **Coordinate Mapping**: SVG viewbox is normalized to world coordinates (e.g., `viewBox="0 0 1000 750"`) to match system physics.
- **Observability**: Real-time log streaming and performance "HUD" (FPS, Latency, Process Status).

## 5. Integration Patterns

### 5.1 Manual Operation

Humans use the dashboard in a standard browser to calibrate the system, manage map assets, or control "DM" actions during gameplay.

### 5.2 UI Automation (WebDriver)

Since the dashboard is a standard web app, it can be driven by tools like **Playwright** or **Selenium**. This enables:

- **End-to-End Testing**: Verifying that dragging the grid in the UI correctly updates the system state.
- **Headless Management**: Automated scripts can perform complex setup routines by driving the UI.
- **Stable Interaction**: Components use `data-testid` attributes for reliable selection in tests.

## 6. Verification Plan

### 6.1 Unit Tests (Frontend)

- Test the `useSystemState` hook logic with a mock WebSocket server.
- Verify coordinate transformation logic (world-to-pixel and pixel-to-world).

### 6.2 Integration Tests (Backend/Frontend)

- Verify that the FastAPI server correctly serves the frontend assets.
- Test the WebSocket broadcast of `state_mirror` updates.
- Verify asset upload and storage persistence via the API.

### 6.3 End-to-End Tests (Playwright)

- **Automated Grid Calibration**: A Playwright script drags the grid handle and verifies the resulting `AppConfig` change.
- **Token Config Flow**: Script opens a token's form, edits its name, and verifies it persists after a page reload.
- **Calibration Wizard Smoke Test**: Verify the UI correctly transitions through calibration steps and displays feedback.
