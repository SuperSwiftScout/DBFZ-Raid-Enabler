"""Cross-platform shortcut creation and management."""

import sys
import stat
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from utils.errors import ShortcutError
from utils.logger import logger

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Windows-only import with type checking support
if TYPE_CHECKING:
    import win32com.client as win32com_client
elif IS_WINDOWS:
    import win32com.client as win32com_client


class ShortcutManager:
    """
    Create and manage shortcuts for launching patched executables.
    Uses Windows .lnk files or Linux .desktop files depending on platform.
    """

    def create_shortcut(
        self,
        target_exe: Path,
        shortcut_path: Path,
        raid_name: str
    ) -> Path:
        """
        Create shortcut with raid name in description.

        Args:
            target_exe: Path to executable the shortcut points to
            shortcut_path: Path where shortcut should be created
            raid_name: Raid boss name for description

        Returns:
            Path to the created shortcut

        Raises:
            ShortcutError: If shortcut creation fails
        """
        if IS_WINDOWS:
            return self._create_windows_shortcut(target_exe, shortcut_path, raid_name)
        elif IS_LINUX:
            return self._create_linux_shortcut(target_exe, shortcut_path, raid_name)
        else:
            raise ShortcutError("Shortcut creation not supported on this platform")

    def _create_windows_shortcut(
        self,
        target_exe: Path,
        shortcut_path: Path,
        raid_name: str
    ) -> Path:
        """Create Windows .lnk shortcut."""
        try:
            logger.info(f"Creating Windows shortcut: {shortcut_path}")

            # Create shell object
            shell = win32com_client.Dispatch("WScript.Shell")

            # Create shortcut object
            shortcut = shell.CreateShortCut(str(shortcut_path))

            # Set properties
            shortcut.TargetPath = str(target_exe)
            shortcut.WorkingDirectory = str(target_exe.parent)
            shortcut.Description = f"DBFZ Raid: {raid_name}"
            shortcut.IconLocation = str(target_exe)  # Use exe icon

            # Save shortcut
            shortcut.save()

            logger.info(f"Windows shortcut created successfully: {raid_name}")
            return shortcut_path

        except Exception as e:
            logger.error(f"Failed to create Windows shortcut: {e}")
            raise ShortcutError(f"Failed to create shortcut: {e}")

    def _create_linux_shortcut(
        self,
        target_exe: Path,
        shortcut_path: Path,
        raid_name: str
    ) -> Path:
        """Create Linux shell script for launching patched exe via Wine/Proton."""
        try:
            # Change extension from .desktop to .sh for shell script
            shortcut_path = shortcut_path.with_suffix('.sh')
            logger.info(f"Creating Linux launch script: {shortcut_path}")

            # Derive the Wine prefix path from the game location
            # Game is at: .../steamapps/common/DRAGON BALL FighterZ/...
            # Prefix is at: .../steamapps/compatdata/678950/pfx
            exe_dir = target_exe.parent
            # Navigate up to steamapps: RED/Binaries/Win64 -> game_root -> common -> steamapps
            steamapps_dir = exe_dir.parent.parent.parent.parent.parent
            wine_prefix = steamapps_dir / "compatdata" / "678950" / "pfx"

            # Create shell script that sets up the patched exe and launches through Steam
            original_exe = target_exe.parent / "RED-Win64-Shipping.exe"
            backup_exe = target_exe.parent / "RED-Win64-Shipping.exe.backup"

            script_content = f'''#!/bin/bash
# DBFZ Raid Enabler - {raid_name}
# Replaces the original exe with the patched one, then launches through Steam
# Use the cleanup option in the patcher to restore the original exe

ORIGINAL_EXE="{original_exe}"
PATCHED_EXE="{target_exe}"
BACKUP_EXE="{backup_exe}"

if [ ! -f "$PATCHED_EXE" ]; then
    echo "Error: Patched executable not found at $PATCHED_EXE"
    read -p "Press Enter to exit..."
    exit 1
fi

# Backup original exe if not already backed up
if [ -f "$ORIGINAL_EXE" ] && [ ! -L "$ORIGINAL_EXE" ] && [ ! -f "$BACKUP_EXE" ]; then
    echo "Backing up original executable..."
    cp "$ORIGINAL_EXE" "$BACKUP_EXE"
fi

# Replace original with patched (copy, not symlink, for better compatibility)
echo "Installing patched executable..."
cp "$PATCHED_EXE" "$ORIGINAL_EXE"

# Launch through Steam
echo "Launching DBFZ through Steam..."
steam steam://rungameid/678950 &

echo ""
echo "Game is launching through Steam."
echo "To restore the original exe, use the cleanup option in the patcher."
'''

            # Write the shell script
            shortcut_path.write_text(script_content, encoding='utf-8')

            # Make it executable
            shortcut_path.chmod(shortcut_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            logger.info(f"Linux launch script created successfully: {raid_name}")
            return shortcut_path

        except Exception as e:
            logger.error(f"Failed to create Linux launch script: {e}")
            raise ShortcutError(f"Failed to create shortcut: {e}")

    def update_shortcut(
        self,
        target_exe: Path,
        shortcut_path: Path,
        raid_name: str
    ) -> Path:
        """
        Update existing shortcut with new raid name.

        Simply deletes old shortcut and creates new one.
        This is simpler than trying to modify the existing shortcut.

        Args:
            target_exe: Path to executable
            shortcut_path: Path to shortcut file
            raid_name: New raid boss name

        Returns:
            Path to the created (updated) shortcut

        Raises:
            ShortcutError: If update fails
        """
        # Delete old shortcut if it exists
        if shortcut_path.exists():
            try:
                logger.info(f"Removing old shortcut: {shortcut_path}")
                shortcut_path.unlink()
            except Exception as e:
                logger.warning(f"Could not remove old shortcut: {e}")
                # Continue anyway - will overwrite

        # Create new shortcut
        return self.create_shortcut(target_exe, shortcut_path, raid_name)

    def get_shortcut_target(self, shortcut_path: Path) -> Optional[str]:
        """
        Read target path from existing shortcut.

        Args:
            shortcut_path: Path to shortcut file

        Returns:
            Target path as string, or None if cannot read
        """
        if not shortcut_path.exists():
            logger.debug(f"Shortcut doesn't exist: {shortcut_path}")
            return None

        if IS_WINDOWS:
            return self._get_windows_shortcut_target(shortcut_path)
        elif IS_LINUX:
            return self._get_linux_shortcut_target(shortcut_path)
        else:
            return None

    def _get_windows_shortcut_target(self, shortcut_path: Path) -> Optional[str]:
        """Read target from Windows .lnk file."""
        try:
            shell = win32com_client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            target = shortcut.TargetPath

            logger.debug(f"Windows shortcut target: {target}")
            return target

        except Exception as e:
            logger.error(f"Failed to read Windows shortcut: {e}")
            return None

    def _get_linux_shortcut_target(self, shortcut_path: Path) -> Optional[str]:
        """Read Exec line from Linux .desktop file."""
        try:
            content = shortcut_path.read_text(encoding='utf-8')
            for line in content.splitlines():
                if line.startswith("Exec="):
                    target = line[5:].strip()
                    logger.debug(f"Linux .desktop target: {target}")
                    return target
            return None

        except Exception as e:
            logger.error(f"Failed to read Linux .desktop file: {e}")
            return None

    def shortcut_exists(self, shortcut_path: Path) -> bool:
        """
        Check if shortcut exists and is valid.

        Args:
            shortcut_path: Path to check

        Returns:
            True if shortcut exists and appears valid
        """
        if not shortcut_path.exists():
            return False

        # Try to read target to verify it's a valid shortcut
        target = self.get_shortcut_target(shortcut_path)
        return target is not None
