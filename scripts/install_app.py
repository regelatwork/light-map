#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path


def build_executable():
    print("Building executable with PyInstaller...")

    # We use the main entry point defined in pyproject.toml
    # light-map = "light_map.__main__:main"

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "light-map",
        "--paths",
        "src",
        "src/light_map_entry.py",
    ]

    subprocess.check_call(cmd)
    print("Build complete.")


def install_binary():
    home = Path.home()
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    src_bin = Path("dist/light-map")
    dest_bin = bin_dir / "light-map"

    print(f"Installing binary to {dest_bin}...")
    shutil.copy2(src_bin, dest_bin)
    dest_bin.chmod(0o755)


def create_desktop_entry():
    home = Path.home()
    apps_dir = home / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = apps_dir / "light-map.desktop"
    bin_path = home / ".local" / "bin" / "light-map"

    # Try to find an icon, or use a default
    icon_path = ""  # TODO: Add icon if available

    content = f"""[Desktop Entry]
Type=Application
Name=Light Map
Comment=Interactive AR tabletop platform
Exec={bin_path}
Terminal=true
Categories=Game;Utility;
"""
    if icon_path:
        content += f"Icon={icon_path}\n"

    print(f"Creating desktop entry at {desktop_file}...")
    with open(desktop_file, "w") as f:
        f.write(content)

    desktop_file.chmod(0o644)


def main():
    try:
        build_executable()
        install_binary()
        create_desktop_entry()
        print("\nInstallation successful!")
        print("You can now run 'light-map' from your terminal or application menu.")
    except Exception as e:
        print(f"Error during installation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
