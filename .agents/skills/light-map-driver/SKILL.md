---
name: light-map-driver
description: Automate and drive the Light Map application via its Remote Driver API. Use when debugging tactical logic, verifying token detection, or performing end-to-end integration tests that require starting the app, stabilizing ArUco detection, and simulating hand/token inputs.
---

# Light Map Driver

This skill standardizes the "Lifecycle Loop" for driving the Light Map application through its API.

## Core Workflow

1. **Start & Stabilize:** Launch the app, wait for the API, and open the menu for 5-10s to improve ArUco contrast for physical tokens.
2. **Interact:** Inject tokens (mock) or Query tokens (physical) and simulate a "Dwell" by pointing at coordinates for 2+ seconds.
3. **Verify:** Check logs and state for tactical results.
4. **Shutdown:** Gracefully close the app using the `QUIT` action.

## Bundled Resources

- **`scripts/drive_app.py`**: A robust lifecycle script. Run it from the skill directory or copy it to the project root.
- **[PHYSICAL_SETUP.md](references/physical-setup.md)**: Guidelines for working with a physical table and minies.
- **[SIMULATED_TESTING.md](references/simulated-testing.md)**: Patterns for mock token injection and headless logic verification.

## Example Triggers

- "Drive the app to verify the wall at X=150."
- "Start the map bd514.svg and check cover for Wendy."
- "Perform a 10-second stabilization run for the physical tokens."
