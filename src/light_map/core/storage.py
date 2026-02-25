import os
from pathlib import Path
from typing import Optional


class StorageManager:
    """
    Manages application directory structure for configuration and data.
    Follows XDG standards on Linux by default.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the StorageManager.

        Args:
            base_dir: Optional override for all storage. If provided, config and data
                      will be subdirectories of this base.
        """
        if base_dir:
            self.base_root = Path(base_dir).absolute()
            self.config_dir = self.base_root / "config"
            self.data_dir = self.base_root / "data"
            self.state_dir = self.base_root / "state"
        else:
            self.base_root = None
            # Default to XDG structures
            home = Path.home()
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            self.config_dir = (
                Path(xdg_config) if xdg_config else home / ".config"
            ) / "light_map"

            xdg_data = os.environ.get("XDG_DATA_HOME")
            self.data_dir = (
                Path(xdg_data) if xdg_data else home / ".local" / "share"
            ) / "light_map"

            xdg_state = os.environ.get("XDG_STATE_HOME")
            self.state_dir = (
                Path(xdg_state) if xdg_state else home / ".local" / "state"
            ) / "light_map"

    def get_config_dir(self) -> str:
        """Returns the directory for configuration files."""
        return str(self.config_dir)

    def get_data_dir(self) -> str:
        """Returns the directory for data files (calibration, sessions)."""
        return str(self.data_dir)

    def get_state_dir(self) -> str:
        """Returns the directory for state files (logs)."""
        return str(self.state_dir)

    def get_config_path(self, filename: str) -> str:
        """Returns the full path for a configuration file."""
        return str(self.config_dir / filename)

    def get_data_path(self, filename: str) -> str:
        """Returns the full path for a data file."""
        return str(self.data_dir / filename)

    def get_state_path(self, filename: str) -> str:
        """Returns the full path for a state file (logs)."""
        return str(self.state_dir / filename)

    def ensure_dirs(self):
        """Creates the managed directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # Also ensure sessions subdir exists in data
        (self.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
