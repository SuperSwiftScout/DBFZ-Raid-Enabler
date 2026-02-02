"""Platform detection and cross-platform utilities."""

import sys
from pathlib import Path

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"


def get_shortcut_extension() -> str:
    """Get the appropriate shortcut file extension for the current platform."""
    if IS_WINDOWS:
        return ".lnk"
    else:
        return ".sh"


def get_shortcut_glob_pattern() -> str:
    """Get glob pattern for raid shortcuts on current platform."""
    if IS_WINDOWS:
        return "DBFZ Raid *.lnk"
    else:
        return "DBFZ Raid *.sh"
