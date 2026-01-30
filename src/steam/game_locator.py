"""Unified Steam and DBFZ game location."""

import winreg
import vdf
from pathlib import Path
from typing import Dict, List, Optional
from utils.errors import SteamNotFoundError, GameNotFoundError
from utils.logger import logger


class GameLocator:
    """
    Unified locator for Steam installation and DBFZ game files.
    Uses Steam's app manifest for efficient, direct game lookup.
    """

    DBFZ_APP_ID = "678950"
    GAME_FOLDER_NAME = "DRAGON BALL FighterZ"
    EXE_RELATIVE_PATH = Path("RED/Binaries/Win64/RED-Win64-Shipping.exe")

    DEFAULT_STEAM_PATHS = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
    ]

    def __init__(self):
        self._steam_path: Optional[Path] = None
        self._library_paths: Optional[List[Path]] = None
        self._game_root: Optional[Path] = None

    def _find_steam_installation(self) -> Optional[Path]:
        """Locate Steam installation via registry, then fallback to default paths."""
        if self._steam_path:
            return self._steam_path

        # Try registry first
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path = Path(winreg.QueryValueEx(key, "SteamPath")[0])
                if steam_path.exists():
                    logger.info(f"Found Steam via registry: {steam_path}")
                    self._steam_path = steam_path
                    return steam_path
        except OSError:
            pass

        # Fallback to default paths
        for path in self.DEFAULT_STEAM_PATHS:
            if path.exists():
                logger.info(f"Found Steam at default path: {path}")
                self._steam_path = path
                return path

        return None

    def _parse_library_folders(self, steam_path: Path) -> List[Path]:
        """Parse libraryfolders.vdf to get all Steam library locations."""
        if self._library_paths:
            return self._library_paths

        vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
        libraries = [steam_path]

        if not vdf_path.exists():
            logger.warning(f"libraryfolders.vdf not found, using main Steam path only")
            self._library_paths = libraries
            return libraries

        try:
            with open(vdf_path, 'r', encoding='utf-8') as f:
                data = vdf.load(f)

            for value in data.get('libraryfolders', {}).values():
                if isinstance(value, dict) and 'path' in value:
                    lib_path = Path(value['path'])
                    if lib_path.exists() and lib_path not in libraries:
                        libraries.append(lib_path)

            logger.info(f"Found {len(libraries)} Steam libraries")
        except Exception as e:
            logger.error(f"Failed to parse libraryfolders.vdf: {e}")

        self._library_paths = libraries
        return libraries

    def _find_game_via_manifest(self, libraries: List[Path]) -> Optional[Path]:
        """
        Find DBFZ by checking for its app manifest in each library.
        This is more efficient than scanning folder structures.
        """
        manifest_name = f"appmanifest_{self.DBFZ_APP_ID}.acf"

        for library in libraries:
            manifest_path = library / "steamapps" / manifest_name
            if manifest_path.exists():
                # Parse manifest to get install directory name
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = vdf.load(f)

                    app_state = manifest.get('AppState', {})
                    install_dir = app_state.get('installdir', self.GAME_FOLDER_NAME)
                    game_path = library / "steamapps" / "common" / install_dir

                    # Verify the executable exists
                    exe_path = game_path / self.EXE_RELATIVE_PATH
                    if exe_path.exists():
                        logger.info(f"Found DBFZ via manifest: {game_path}")
                        return game_path
                    else:
                        logger.warning(f"Manifest found but executable missing: {exe_path}")
                except Exception as e:
                    logger.error(f"Failed to parse manifest {manifest_path}: {e}")

        return None

    def _find_game_via_folder_scan(self, libraries: List[Path]) -> Optional[Path]:
        """Fallback: scan for game folder directly if manifest lookup fails."""
        for library in libraries:
            game_path = library / "steamapps" / "common" / self.GAME_FOLDER_NAME
            exe_path = game_path / self.EXE_RELATIVE_PATH

            if exe_path.exists():
                logger.info(f"Found DBFZ via folder scan: {game_path}")
                return game_path

        return None

    def get_all_library_paths(self) -> List[Path]:
        """
        Get all Steam library paths.

        Returns:
            List of Steam library paths

        Raises:
            SteamNotFoundError: If Steam is not installed
        """
        steam_path = self._find_steam_installation()
        if not steam_path:
            raise SteamNotFoundError("Steam installation not found.")
        return self._parse_library_folders(steam_path)

    def find_dbfz_installation(self, library_paths: List[Path]) -> Optional[Path]:
        """
        Find DBFZ installation across Steam libraries.

        Args:
            library_paths: List of Steam library directories

        Returns:
            Path to game root or None if not found
        """
        if self._game_root:
            return self._game_root

        # Try manifest-based lookup first (fast)
        game_root = self._find_game_via_manifest(library_paths)

        # Fallback to folder scan
        if not game_root:
            game_root = self._find_game_via_folder_scan(library_paths)

        if game_root:
            self._game_root = game_root

        return game_root

    def get_file_paths(self, game_root: Path) -> Dict[str, Path]:
        """
        Get all relevant file paths for operations.

        Args:
            game_root: Path to DBFZ installation root

        Returns:
            Dictionary with file paths
        """
        exe_dir = game_root / "RED" / "Binaries" / "Win64"
        eac_dir = game_root / "EasyAntiCheat"

        return {
            'game_root': game_root,
            'clean_exe': exe_dir / "RED-Win64-Shipping.exe",
            'patched_exe': exe_dir / "RED-Win64-Shipping-eac-nop-loaded.exe",
            'eac_setup': eac_dir / "EasyAntiCheat_Setup.exe",
            'eac_directory': eac_dir,
            'exe_directory': exe_dir
        }

    def validate_installation(self, game_root: Path) -> bool:
        """
        Validate that DBFZ installation has required files.

        Args:
            game_root: Path to game installation

        Returns:
            True if installation is valid
        """
        paths = self.get_file_paths(game_root)

        if not paths['clean_exe'].exists():
            logger.error(f"Game executable not found: {paths['clean_exe']}")
            return False

        if not paths['exe_directory'].exists():
            logger.error(f"Binaries directory not found: {paths['exe_directory']}")
            return False

        return True

    def find_and_validate(self, library_paths: List[Path]) -> Dict[str, Path]:
        """
        Find DBFZ installation and return validated file paths.

        Args:
            library_paths: List of Steam library directories

        Returns:
            Dictionary of file paths

        Raises:
            GameNotFoundError: If DBFZ not found or installation invalid
        """
        game_root = self.find_dbfz_installation(library_paths)

        if not game_root:
            raise GameNotFoundError(
                "Dragon Ball FighterZ not found in any Steam library."
            )

        if not self.validate_installation(game_root):
            paths = self.get_file_paths(game_root)
            if not paths['exe_directory'].exists():
                raise GameNotFoundError(
                    f"\nGame folder found but installation is incomplete (missing RED/Binaries/Win64).\n"
                    "Verify game files: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity\n"
                    "If that doesn't work, reinstall the game\n"
                )
            else:
                raise GameNotFoundError(
                    f"\nGame folder found but executable is missing ({paths['clean_exe'].name}).\n"
                    "Verify game files: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity\n"
                    "If that doesn't work, reinstall the game"
                )

        return self.get_file_paths(game_root)
