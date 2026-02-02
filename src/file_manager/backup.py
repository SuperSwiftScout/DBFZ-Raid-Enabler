"""Backup management for clean game executable."""

import shutil
import logging
from pathlib import Path
from typing import Optional, Callable
from utils.errors import BackupError
from utils.logger import logger
from utils.platform import get_shortcut_glob_pattern, IS_LINUX


class BackupManager:
    """
    Manage clean backup and patched executable lifecycle.
    """

    def verify_clean_exe(self, clean_exe: Path) -> bool:
        """
        Verify that clean exe exists.

        Args:
            clean_exe: Path to original game executable

        Returns:
            True if clean exe exists

        Raises:
            BackupError: If clean exe doesn't exist
        """
        if not clean_exe.exists():
            logger.error(f"Clean executable not found: {clean_exe}")
            raise BackupError(
                f"Original game executable not found at {clean_exe}. "
                "Please verify game files via Steam."
            )

        logger.info(f"Clean exe verified: {clean_exe}")
        return True

    def create_or_update_patched_exe(
        self,
        clean_exe: Path,
        patched_exe: Path
    ) -> Path:
        """
        Create/update patched exe from clean exe.

        This workflow ensures we always patch from a clean source:
        1. Verify clean exe exists
        2. Delete old patched exe if it exists
        3. Copy clean exe to patched exe location
        4. Return path to patched exe for patching

        Args:
            clean_exe: Path to original executable (never modified)
            patched_exe: Path to patched executable (will be created/overwritten)

        Returns:
            Path to patched exe (ready for patching)

        Raises:
            BackupError: If any operation fails
        """
        # Verify clean exe exists
        self.verify_clean_exe(clean_exe)

        # Remove old patched exe if it exists
        if patched_exe.exists():
            try:
                logger.info(f"Removing old patched exe: {patched_exe}")
                patched_exe.unlink()
            except Exception as e:
                logger.warning(f"Could not remove old patched exe: {e}")
                # Continue anyway - copy will overwrite

        # Copy clean exe to patched exe location
        try:
            logger.info(f"Creating fresh patched exe from clean exe")
            shutil.copy2(clean_exe, patched_exe)
            logger.info(f"Patched exe ready: {patched_exe}")
            return patched_exe
        except Exception as e:
            logger.error(f"Failed to create patched exe: {e}")
            raise BackupError(f"Failed to create patched exe: {e}")

    def detect_current_patch(self, patched_exe: Path) -> Optional[int]:
        """
        Detect which raid is currently patched (if any).

        Scans the patched exe for the raid index in the known patch pattern.
        Looks for: B8 [4 bytes] 90 (mov eax, immediate; nop)

        Args:
            patched_exe: Path to patched executable

        Returns:
            Raid index (1-38) or None if not patched or cannot detect
        """
        if not patched_exe.exists():
            logger.debug("Patched exe doesn't exist")
            return None

        try:
            exe_data = patched_exe.read_bytes()

            # Look for pattern: B8 [4 bytes] 90
            pattern_start = 0xB8
            pattern_end = 0x90

            for i in range(len(exe_data) - 5):
                if exe_data[i] == pattern_start and exe_data[i + 5] == pattern_end:
                    # Extract 4-byte raid index (little-endian)
                    raid_bytes = exe_data[i + 1:i + 5]
                    raid_index = int.from_bytes(raid_bytes, byteorder='little')

                    # Validate raid index (1-38)
                    if 1 <= raid_index <= 38:
                        logger.info(f"Detected current patch: Raid {raid_index}")
                        return raid_index

            logger.debug("No valid raid patch detected")
            return None

        except Exception as e:
            logger.error(f"Failed to detect current patch: {e}")
            return None

    def install_patched_exe_linux(self, patched_exe: Path) -> bool:
        """
        Install patched exe by copying it over the original (Linux only).

        This backs up the original exe first, then copies the patched exe
        over the original so Steam launches the patched version.

        Args:
            patched_exe: Path to the patched executable

        Returns:
            True if installation succeeded
        """
        if not IS_LINUX:
            return False

        exe_dir = patched_exe.parent
        original_exe = exe_dir / "RED-Win64-Shipping.exe"
        backup_exe = exe_dir / "RED-Win64-Shipping.exe.backup"

        try:
            # Backup original exe if not already backed up
            if original_exe.exists() and not backup_exe.exists():
                logger.info(f"Backing up original exe to: {backup_exe}")
                shutil.copy2(original_exe, backup_exe)

            # Copy patched exe over original
            logger.info(f"Installing patched exe over original")
            shutil.copy2(patched_exe, original_exe)

            logger.info("Patched exe installed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to install patched exe: {e}")
            return False

    def cleanup_all(self, patched_exe: Path, game_root: Path, progress_callback: Optional[Callable[[str], None]] = None) -> dict:
        """
        Clean up all modifications made by the program.

        Removes:
        - Patched executable
        - All raid shortcuts (in game folder)
        - Application log directory (~/.dbfz_raid_enabler)

        On Linux:
        - Restores original executable from backup (created by launch script)

        Args:
            patched_exe: Path to patched executable
            game_root: Path to game root directory
            progress_callback: Optional callable that receives status messages to be shown to the user

        Returns:
            Dictionary with cleanup results:
            {
                'patched_exe_removed': bool,
                'original_restored': bool,  # Linux only
                'shortcuts_removed': int,
                'logs_removed': bool,
                'errors': [str]
            }
        """
        import os

        results = {
            'patched_exe_removed': False,
            'original_restored': False,
            'shortcuts_removed': 0,
            'logs_removed': False,
            'errors': []
        }

        # Remove patched exe
        if patched_exe.exists():
            try:
                if progress_callback:
                    progress_callback("Removing patched executable...")
                logger.info(f"Removing patched exe: {patched_exe}")
                patched_exe.unlink()
                results['patched_exe_removed'] = True
                logger.info("Patched exe removed successfully")
            except Exception as e:
                error_msg = f"Failed to remove patched exe: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        else:
            logger.info("Patched exe not found, nothing to remove")

        # On Linux, restore original exe from backup if it exists
        # The shell script creates a backup at RED-Win64-Shipping.exe.backup
        if IS_LINUX:
            exe_dir = patched_exe.parent
            original_exe = exe_dir / "RED-Win64-Shipping.exe"
            backup_exe = exe_dir / "RED-Win64-Shipping.exe.backup"

            if backup_exe.exists():
                try:
                    if progress_callback:
                        progress_callback("Restoring original executable...")
                    logger.info(f"Restoring original exe from backup: {backup_exe}")
                    shutil.copy2(backup_exe, original_exe)
                    backup_exe.unlink()
                    results['original_restored'] = True
                    logger.info("Original exe restored successfully")
                except Exception as e:
                    error_msg = f"Failed to restore original exe: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            else:
                logger.info("No backup found, original exe may not have been replaced")

        # Update status
        if progress_callback:
            progress_callback("Removing raid shortcuts...")

        # Remove all shortcuts in game root folder
        try:
            for shortcut in game_root.glob(get_shortcut_glob_pattern()):
                try:
                    logger.info(f"Removing shortcut: {shortcut.name}")
                    shortcut.unlink()
                    results['shortcuts_removed'] += 1
                except Exception as e:
                    error_msg = f"Failed to remove shortcut {shortcut.name}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
        except Exception as e:
            error_msg = f"Error scanning for shortcuts in game folder: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)

        # Update status
        if progress_callback:
            progress_callback("Removing application logs...")

        # Remove application logs directory created by the program
        log_dir = Path.home() / ".dbfz_raid_enabler"
        try:
            if log_dir.exists():
                if progress_callback:
                    progress_callback("Closing log file handles...")
                logger.info(f"Preparing to remove application logs directory: {log_dir}")

                # Try to close any file handlers that might be holding files open in the logs dir
                try:
                    for handler in logger.handlers[:]:
                        try:
                            base_filename = getattr(handler, 'baseFilename', None)
                            if base_filename:
                                handler_path = Path(base_filename).resolve()
                                try:
                                    log_dir_resolved = log_dir.resolve()
                                except Exception:
                                    log_dir_resolved = log_dir
                                if log_dir_resolved == handler_path or log_dir_resolved in handler_path.parents:
                                    logger.debug(f"Closing log handler for file: {base_filename}")
                                    try:
                                        handler.flush()
                                    except Exception:
                                        pass
                                    try:
                                        handler.close()
                                    except Exception:
                                        pass
                                    try:
                                        logger.removeHandler(handler)
                                    except Exception:
                                        pass
                        except Exception as e:
                            logger.warning(f"Could not close handler {handler}: {e}")
                except Exception as e:
                    logger.warning(f"Failed while attempting to close log handlers: {e}")

                shutil.rmtree(log_dir)
                results['logs_removed'] = True
                logger.info("Logs directory removed successfully")
            else:
                logger.info("Logs directory not found, nothing to remove")
        except Exception as e:
            error_msg = f"Failed to remove logs directory {repr(log_dir)}: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            # Critical: failing to remove logs should abort the whole cleanup
            raise BackupError(error_msg)

        return results
