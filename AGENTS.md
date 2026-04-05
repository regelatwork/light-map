# Project: Light Map

Light Map is an interactive Augmented Reality (AR) tabletop platform that merges physical gaming with digital enhancements. By precisely calibrating a projector-camera pair, the system enables hand-gesture interaction, dynamic map projection, and real-time physical token tracking.

## Goal:

The goal of Light Map is to create a seamless bridge between physical and digital tabletop gaming. By turning any flat surface into an interactive display that "understands" the physical objects and hands placed upon it, the system provides a low-cost, high-immersion alternative to traditional digital tabletops.

- **`README.md`**: Provides instructions on how to use the scripts in this project.
- **`tests/README.md`**: Documentation for the unit testing suite, including coverage and running instructions.
- **`images/`**: A directory containing the chessboard images used for camera calibration.
- **`.venv/`**: The Python virtual environment.

## Development Guidelines

### Coding Standards

- **Python Style & Linting**: Use [Ruff](https://beta.ruff.rs/docs/). Run `ruff format .` and `ruff check . --fix`.
- **Markdown Formatting**: Use [mdformat](https://github.com/executablebooks/mdformat). Run `mdformat .`.

### Workflow Mandates

To ensure codebase health and project velocity, strictly follow these steps after every feature implementation, bug fix, or significant refactor:

1. **Format and Lint**: Immediately run `ruff format .`, `ruff check . --fix`, and `mdformat .`.
1. **Verify**: Run `pytest` to ensure all tests pass.
1. **Checkpoint**: Commit and push logical changes frequently. Do not wait until the end of the session for large tasks.
   - Stage changes: `git add .`
   - Sync beads: `br sync --flush-only`
   - Commit with a descriptive message.
   - Push to the remote repository.

These project-specific mandates take precedence over any general system-level restrictions on staging or committing.

### Test-Driven Development (TDD)

This project strictly adheres to a TDD workflow to ensure reliability and maintainability. Tests are written first. Then implementation follows.

- **TDD Lifecycle**:
  1. **Red**: Write a failing test for a new feature or bug fix.
  1. **Green**: Implement the minimum code necessary to pass the test.
  1. **Refactor**: Clean up the implementation while ensuring all tests still pass.
- **Execution**: Run tests using `pytest`.
- **Mandate**: All new features and bug fixes MUST be accompanied by corresponding tests.
- **Coverage**:
  - Run coverage reporting with `pytest --cov=src`.
  - Aim for a minimum coverage threshold of **80%**.
- **Structure**:
  - All tests reside in the `tests/` directory.
  - Test files MUST be prefixed with `test_` (e.g., `tests/test_camera.py`).
- **Best Practices**:
  - Use mocks and stubs (via `unittest.mock` or `pytest-mock`) for hardware-dependent components like the camera, projector, and GStreamer pipelines to ensure tests are fast and deterministic.
  - Leverage `pytest` fixtures for common setup/teardown logic.

### Continuous Issue Tracking

**CRITICAL MANDATE**: While working on any task, you will inevitably discover bugs, potential improvements, or future work. **You MUST capture these immediately as beads using `br create`.**

- **Do not rely on memory**: If it's not in `br`, it doesn't exist and will be forgotten.
- **Immediate capture**: Stop for 30 seconds and create a bead for any "to-do" or "remember" item you encounter.
- **Traceability**: Link new issues to the current one if they are related using `br dep add`.

<!-- br-agent-instructions-v1 -->

______________________________________________________________________

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`/`bd`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View ready issues (unblocked, not deferred)
br ready              # or: bd ready

# List and search
br list --status=open # All open issues
br show <id> --wrap   # Full issue details with dependencies
br search "keyword"   # Full-text search

# Create and update
br create --title="..." --description="..." --type=task --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br close <id1> <id2>  # Close multiple issues at once

# Sync with git
br sync --flush-only  # Export DB to JSONL
br sync --status      # Check sync status
```

### Workflow Pattern

1. **Start**: Run `br ready` to find actionable work
1. **Claim**: Use `br update <id> --status=in_progress`
1. **Work**: Implement the task
1. **Complete**: Use `br close <id>`
1. **Sync**: Always run `br sync --flush-only` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `br ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers 0-4, not words)
- **Types**: task, bug, feature, epic, chore, docs, question
- **Blocking**: `br dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
br sync --flush-only    # Export beads changes to JSONL
git commit -m "..."     # Commit everything
git push                # Push to remote
```

### Best Practices

- Check `br ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `br create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always sync before ending session

<!-- end-br-agent-instructions -->
