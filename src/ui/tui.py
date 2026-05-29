"""Terminal UI for DBFZ Raid Enabler."""

import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markup import escape
from rich import box
from pathlib import Path
from typing import Optional, Dict, Union

from core.patcher import BinaryPatcher
from core.raid_data import get_all_raids_with_bosses, CHARACTER_CODES
from core.custom_raid import CustomRaid, RaidBattle, list_saved_raids, CUSTOM_RAIDS_DIR
from core.aes_key import get_aes_key, validate_user_key
from steam.game_locator import GameLocator
from file_manager.backup import BackupManager
from file_manager.shortcut import ShortcutManager
from utils.errors import (
    DBFZRaidError,
    SteamNotFoundError,
    GameNotFoundError,
    AESKeyError,
    PakError,
)
from utils.logger import logger

# Raid slot used for custom raids — chosen for its generic name
CUSTOM_RAID_SLOT = 38

_DEFAULT_BACKGROUNDS = [
    "Town_PL",
    "Wasteland_PL",
    "Volcano_PL",
    "TownDestroy_PL",
    "Space_PL",
    "Kaiousinkai_PL",
    "Rocky_PL",
]
_DEFAULT_BGM = "035_main_raid"
_DEFAULT_SKILL_NUM = 506


class DBFZRaidTUI:
    """
    Main TUI controller using rich library.
    """

    def __init__(self):
        self.console = Console()
        self.patcher = BinaryPatcher()
        self.game_locator = GameLocator()
        self.backup_manager = BackupManager()
        self.shortcut_manager = ShortcutManager()

    def run(self):
        """Main application loop."""
        try:
            self.show_header()

            # Step 1: Detect Steam and DBFZ
            game_info = self.detect_game()
            if not game_info:
                self.console.print()
                self.console.print("[yellow]Operation cancelled.[/yellow]")
                return

            # Step 2: Enter main menu loop (allows returning to selection on cancel)
            while True:
                # Check current patch status each loop iteration
                current_raid = self.check_current_patch(game_info)

                # Step 3: Show raid selection menu
                selection = self.show_raid_menu(current_raid)
                if not selection:
                    self.console.print("[yellow]Operation cancelled.[/yellow]")
                    return

                # Step 4: Execute workflow based on selection
                if selection == 'cleanup':
                    cleanup_result = self.execute_cleanup_workflow(game_info)

                    # If user cancelled the cleanup, return to selection loop
                    if cleanup_result is False:
                        continue

                    # After cleanup attempt (successful or failed), exit app
                    return
                elif selection == 'custom_raid':
                    result = self.show_custom_raid_menu(game_info)
                    if result is False:
                        continue
                    return
                elif isinstance(selection, int):
                    result = self.execute_patch_workflow(game_info, selection, current_raid)
                    if result is False:
                        # User cancelled re-patch, return to menu
                        continue
                    return

        except KeyboardInterrupt:
            self.console.print()
            self.console.print("[yellow]Operation cancelled.[/yellow]")
        except DBFZRaidError as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
            logger.exception("Application error")
        except Exception as e:
            self.console.print(f"\n[red]Unexpected error: {e}[/red]")
            logger.exception("Unexpected error")

    def show_header(self):
        """Display application header."""
        header = Panel(
            "[bold cyan]DBFZ Raid Enabler[/bold cyan]\n"
            "[dim]Version 1.2.3[/dim]\n"
            "[dim]Intended for DBFZ Version 1.50[/dim]\n"
            "[dim]Python tool to patch Dragon Ball FighterZ to enable raid battles again.[/dim]",
            box=box.DOUBLE,
            border_style="cyan"
        )
        self.console.print(header)
        self.console.print()

    def detect_game(self) -> Optional[Dict]:
        """
        Detect Steam and DBFZ installation with progress indicator.

        Returns:
            Dictionary with game_root and paths, or None if not found
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            task = progress.add_task("Detecting Steam installation...", total=None)

            # Find Steam libraries
            try:
                libraries = self.game_locator.get_all_library_paths()
            except SteamNotFoundError as e:
                progress.stop()
                self.console.print(f"[red]{e}[/red]")
                # Offer manual path input as fallback
                return self.manual_game_path_input()

            progress.update(task, description="Locating DBFZ installation...")

            # Find DBFZ
            try:
                paths = self.game_locator.find_and_validate(libraries)
            except GameNotFoundError as e:
                progress.stop()
                error_msg = str(e)

                # Check if game was found but corrupted (vs not found at all)
                if "found but" in error_msg.lower():
                    # Game folder exists but files are missing - show error and exit
                    self.console.print()
                    self.console.print(f"[red]{error_msg}[/red]")
                    self.console.print()
                    self.console.print("[dim]Press Enter to exit...[/dim]")
                    input()
                    sys.exit(0)

                self.console.print(f"[yellow]Game not found in Steam libraries. Checking common paths...[/yellow]")

                # Try common paths as fallback
                self._found_corrupted_installation = False
                game_root = self.check_common_paths_with_output()

                # If corruption was detected, just wait for Enter to exit
                if self._found_corrupted_installation:
                    self.console.print()
                    self.console.print("[dim]Press Enter to exit...[/dim]")
                    input()
                    sys.exit(0)

                if game_root and self.game_locator.validate_installation(game_root):
                    paths = self.game_locator.get_file_paths(game_root)
                    self.console.print()
                    self.console.print(f"[green]✓ Found DBFZ at:[/green] [cyan]{game_root}[/cyan]")
                    self.console.print()
                    return {'game_root': game_root, 'paths': paths}

                # If common paths also failed, offer manual input
                self.console.print()
                self.console.print("[yellow]Common installation paths also checked with no success.[/yellow]")
                # Offer manual path input as final fallback
                return self.manual_game_path_input()

            progress.update(task, description="Game found!", completed=True)
            # Ensure final render before context exit so spinner doesn't leave a stale character
            try:
                progress.refresh()
            except Exception:
                pass

        game_root = paths['game_root']
        self.console.print(f"[green]✓ Found DBFZ at:[/green] [cyan]{game_root}[/cyan]")
        self.console.print()

        return {'game_root': game_root, 'paths': paths}

    def check_common_paths_with_output(self) -> Optional[Path]:
        """
        Check common paths and show progress to user.

        Returns:
            Path to game root if found, None otherwise
        """
        # Check multiple case variations and path formats
        base_paths = [
            (r"C:\Program Files (x86)\Steam", r"c:\program files (x86)\steam"),
            (r"C:\Program Files\Steam", r"c:\program files\steam"),
            (r"D:\SteamLibrary", r"d:\steamlibrary"),
            (r"D:\Steam", r"d:\steam"),
            (r"E:\SteamLibrary", r"e:\steamlibrary"),
            (r"E:\Steam", r"e:\steam"),
        ]

        for base_upper, base_lower in base_paths:
            # Try both upper and lower case variations
            for base in [base_upper, base_lower]:
                game_path = Path(base) / "steamapps" / "common" / "DRAGON BALL FighterZ"
                exe_path = game_path / "RED" / "Binaries" / "Win64" / "RED-Win64-Shipping.exe"

                # Normalize the path (resolve any .. or . and make absolute)
                try:
                    exe_path = exe_path.resolve()
                except:
                    pass

                # Convert to absolute string path for consistency
                exe_path_str = os.path.abspath(str(exe_path))

                # Try multiple methods to check file existence
                exists_via_path = False
                exists_via_file = False
                exists_via_os = False
                exists_is_file_os = False
                exists_via_access = False

                errors = []

                try:
                    exists_via_path = exe_path.exists()
                except Exception as e:
                    errors.append(f"Path.exists error: {e}")

                try:
                    exists_via_file = exe_path.is_file()
                except Exception as e:
                    errors.append(f"Path.is_file error: {e}")

                # Also try with os.path (more robust on Windows)
                try:
                    exists_via_os = os.path.exists(exe_path_str)
                except Exception as e:
                    errors.append(f"os.path.exists error: {e}")

                try:
                    exists_is_file_os = os.path.isfile(exe_path_str)
                except Exception as e:
                    errors.append(f"os.path.isfile error: {e}")

                # Try os.access (most reliable on Windows, especially in frozen apps)
                try:
                    exists_via_access = os.access(exe_path_str, os.R_OK)
                except Exception as e:
                    errors.append(f"os.access error: {e}")

                # Log any errors encountered
                if errors:
                    for error in errors:
                        logger.error(error)
                        self.console.print(f"    [red]{error}[/red]")

                # Log what we found
                logger.info(f"Checking: {exe_path_str}")
                logger.info(f"  Path.exists(): {exists_via_path}, Path.is_file(): {exists_via_file}")
                logger.info(f"  os.path.exists(): {exists_via_os}, os.path.isfile(): {exists_is_file_os}")
                logger.info(f"  os.access(R_OK): {exists_via_access}")

                # If any method says it exists, accept it
                if exists_via_path or exists_via_file or exists_via_os or exists_is_file_os or exists_via_access:
                    self.console.print(f"  [green]→ Found![/green]")
                    logger.info(f"Found DBFZ at: {game_path}")
                    return game_path
                else:
                    # If this is the first path (most likely), check what's in the directory
                    if base == base_paths[0][0]:  # First path, first case
                        parent_dir = os.path.dirname(exe_path_str)
                        if os.path.exists(parent_dir):
                            try:
                                files = os.listdir(parent_dir)
                                logger.info(f"  Directory exists. Files in {parent_dir}:")
                                logger.info(f"    {files}")
                                self.console.print(f"[red]Game folder found but executable is missing.[/red]")
                                self.console.print(f"[cyan]Verify game files: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity[/cyan]")
                                self.console.print(f"[cyan]If that doesn't work, reinstall the game[/cyan]")
                                self._found_corrupted_installation = True
                            except Exception as e:
                                logger.error(f"  Could not list directory: {e}")
                        else:
                            # Check if game root exists
                            game_root_str = str(game_path)
                            if os.path.exists(game_root_str):
                                logger.info(f"  Game root exists but Win64 directory missing: {game_root_str}")
                                self.console.print(f"[red]\nGame folder found but installation is incomplete.[/red]")
                                self.console.print(f"[cyan]Verify game files: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity[/cyan]")
                                self.console.print(f"[cyan]If that doesn't work, reinstall the game[/cyan]")
                                self._found_corrupted_installation = True
                            else:
                                logger.info(f"  Game not installed at: {game_root_str}")

        return None

    def manual_game_path_input(self) -> Optional[Dict]:
        """
        Prompt user to manually enter game path when automatic detection fails.

        Returns:
            Dictionary with game_root and paths, or None if cancelled/invalid

        Raises:
            KeyboardInterrupt: If user chooses to quit (for clean exit handling)
        """
        self.console.print()
        self.console.print("[red]Automatic detection failed. You can manually enter the game path.[/red]")
        self.console.print("[dim]Example: C:\\Program Files (x86)\\Steam\\steamapps\\common\\DRAGON BALL FighterZ[/dim]")
        self.console.print()

        while True:
            try:
                user_input = Prompt.ask(
                    "Enter game path, 'c' for cleanup, or 'q' to quit",
                    console=self.console
                )

                if user_input.lower() == 'q':
                    return None

                if user_input.lower() == 'c':
                    # Clean up logs only (no game path needed)
                    self.execute_logs_cleanup()
                    continue

                # Skip empty input
                if not user_input.strip():
                    continue

                # Clean up the input path
                game_path = Path(user_input.strip().strip('"').strip("'"))

                # Validate the path
                if not game_path.exists():
                    self.console.print(f"[red]Path does not exist: {game_path}[/red]")
                    continue

                if not game_path.is_dir():
                    self.console.print(f"[red]Path is not a directory: {game_path}[/red]")
                    continue

                # Validate it's a valid DBFZ installation with specific error messages
                paths = self.game_locator.get_file_paths(game_path)
                exe_path = paths['clean_exe']
                exe_dir = paths['exe_directory']
                red_folder = game_path / "RED"

                # Check if this even looks like DBFZ (has RED folder)
                if not red_folder.exists():
                    self.console.print(f"[red]Not a valid DBFZ installation folder.[/red]")
                    self.console.print(f"[dim]Expected to find 'RED' folder inside the game directory.[/dim]")
                    continue

                if not exe_dir.exists():
                    self.console.print(f"[red]Game folder found but installation is incomplete.[/red]")
                    self.console.print(f"[dim]Missing: RED/Binaries/Win64 folder[/dim]")
                    self.console.print(f"[cyan]Verify game files: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity[/cyan]")
                    self.console.print(f"[cyan]If that doesn't work, reinstall the game[/cyan]")
                    continue

                if not exe_path.exists():
                    self.console.print(f"[red]Game folder found but executable is missing.[/red]")
                    self.console.print(f"[dim]Missing: {exe_path.name}[/dim]")
                    self.console.print(f"[cyan]Verify game files: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity[/cyan]")
                    self.console.print(f"[cyan]If that doesn't work, reinstall the game[/cyan]")
                    continue

                # Success - generate paths
                paths = self.game_locator.get_file_paths(game_path)
                self.console.print(f"[green]✓ Found DBFZ at:[/green] [cyan]{game_path}[/cyan]")
                self.console.print()

                return {'game_root': game_path, 'paths': paths}

            except KeyboardInterrupt:
                self.console.print()  # complete the interrupted line
                return None
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                logger.exception("Error in manual path input")

    def check_current_patch(self, game_info: Dict) -> Optional[int]:
        """
        Check if a raid is currently patched.

        Args:
            game_info: Dictionary with game paths

        Returns:
            Current raid index or None
        """
        paths = game_info['paths']
        return self.backup_manager.detect_current_patch(paths['patched_exe'])

    def show_raid_menu(self, current_raid: Optional[int]) -> Union[int, str, None]:
        """
        Display interactive raid selection menu.

        Args:
            current_raid: Currently patched raid index (or None)

        Returns:
            Selected raid index (int), 'cleanup' for cleanup, or None if cancelled
        """
        raids = get_all_raids_with_bosses()

        # Create table
        table = Table(
            title="Vanilla Raid Table",
            caption="[dim]Note: Only one raid can be active at a time[/dim]",
            show_header=True,
            header_style="bold magenta",
            show_lines=True
        )
        table.add_column("#", style="cyan", justify="right", width=4)
        table.add_column("Raid Name", style="white", no_wrap=False)
        table.add_column("Risk", style="red", justify="left", width=7)
        table.add_column("Final Boss", style="yellow", no_wrap=False, width=22)
        table.add_column("Enemies", style="dim", no_wrap=False)

        # Add rows (escape to prevent Rich markup interpretation)
        for idx, name, boss, characters, risk in raids:
            risk_stars = "★" * risk
            table.add_row(str(idx), escape(name), risk_stars, escape(boss), escape(characters))

        self.console.print(table)
        self.console.print()

        # Show current patch below the table
        if current_raid:
            self.console.print(f"[yellow]Current patch:[/yellow] Raid {current_raid}")
            self.console.print()

        # Prompt for selection
        while True:
            try:
                choice = Prompt.ask(
                    "Select a raid (1-39), 'r' for custom raid, 'c' to cleanup, or 'q' to quit",
                    console=self.console
                )

                choice_lower = choice.lower()

                if choice_lower == 'q':
                    self.console.print()
                    return None

                if choice_lower == 'c':
                    return 'cleanup'

                if choice_lower == 'r':
                    return 'custom_raid'

                raid_idx = int(choice)
                if 1 <= raid_idx <= 39:
                    return raid_idx
                else:
                    self.console.print("[red]Invalid raid number. Must be 1-39.[/red]")

            except ValueError:
                self.console.print("[red]Invalid input. Enter a number, 'c' for cleanup, or 'q'.[/red]")
            except KeyboardInterrupt:
                self.console.print()  # complete the interrupted line
                self.console.print()  # blank line for visual separation
                return None

    def execute_patch_workflow(
        self,
        game_info: Dict,
        raid_index: int,
        current_raid: Optional[int]
    ):
        """
        Execute complete patching workflow with progress feedback.

        Args:
            game_info: Dictionary with game paths
            raid_index: Raid to patch
            current_raid: Currently patched raid (if any)
        """
        paths = game_info['paths']
        game_root = game_info['game_root']

        # Check if already patched
        if current_raid == raid_index:
            self.console.print(f"\n[orange1]Raid {raid_index} is already active![/orange1]")
            self.console.print()
            if not Confirm.ask("Do you want to re-patch anyway?", default=False):
                return False  # Signal to return to menu

        self.console.print(f"\n[bold]Patching for: Raid {raid_index}[/bold]\n")

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console, transient=True) as progress:
            task = progress.add_task("Processing...", total=4)

            # Step 1: Verify clean exe
            progress.update(task, description="Verifying clean exe...")
            try:
                self.backup_manager.verify_clean_exe(paths['clean_exe'])
                self.console.print("[green]✓ Clean exe verified[/green]")
            except Exception as e:
                self.console.print(f"[red]✗ Verification failed: {e}[/red]")
                return

            progress.advance(task)

            # Step 2: Prepare patched exe
            progress.update(task, description="Preparing patched executable...")
            try:
                self.backup_manager.create_or_update_patched_exe(
                    paths['clean_exe'],
                    paths['patched_exe']
                )
                self.console.print("[green]✓ Patched executable created[/green]")
            except Exception as e:
                self.console.print(f"[red]✗ Failed to create patched exe: {e}[/red]")
                return

            progress.advance(task)

            # Step 3: Apply patches
            progress.update(task, description="Applying binary patches...")
            try:
                result = self.patcher.patch_executable(paths['patched_exe'], raid_index)

                if not result['success']:
                    self.console.print("[red]✗ Patching failed:[/red]")
                    for error in result['errors']:
                        self.console.print(f"  [red]• {error}[/red]")
                    return

                self.console.print("[green]✓ Binary patches applied[/green]")
            except Exception as e:
                self.console.print(f"[red]✗ Patching error: {e}[/red]")
                return

            progress.advance(task)

            # Step 4: Create shortcuts
            progress.update(task, description="Creating shortcuts...")

            # Delete old shortcuts before creating new one
            try:
                for old_shortcut in game_root.glob("DBFZ Raid *.lnk"):
                    try:
                        logger.info(f"Removing old shortcut: {old_shortcut.name}")
                        old_shortcut.unlink()
                    except Exception as e:
                        logger.warning(f"Could not remove old shortcut: {e}")
            except Exception as e:
                logger.warning(f"Error scanning for old shortcuts: {e}")

            # Generate shortcut filename
            shortcut_name = f"DBFZ Raid {raid_index}.lnk"
            shortcut_path = game_root / shortcut_name

            try:
                self.shortcut_manager.create_shortcut(
                    paths['patched_exe'],
                    shortcut_path,
                    f"Raid {raid_index}"
                )
                self.console.print(f"[green]✓ Shortcut created: {shortcut_name}[/green]")
            except Exception as e:
                self.console.print(f"[yellow]⚠ Shortcut creation failed: {e}[/yellow]")
                # Non-critical, continue

            progress.advance(task)

        # Success message with EAC warning
        self.console.print()

        # EAC Warning Panel
        eac_panel = Panel(
            f"[bold yellow]IMPORTANT: EasyAntiCheat[/bold yellow]\n\n"
            f"You need to manually uninstall EasyAntiCheat for the patch to work.\n"
            f"[bold yellow]→ You can disregard this message if you have already uninstalled EasyAntiCheat.[/bold yellow]\n\n"
            f"[bold]To uninstall EAC:[/bold]\n"
            f"Run: [cyan]{escape(str(game_root))}\\EasyAntiCheat\\EasyAntiCheat_Setup.exe[/cyan]\n"
            f"Then click 'Uninstall'",
            box=box.ROUNDED,
            border_style="yellow",
            title="Action May Be Required"
        )
        self.console.print(eac_panel)
        self.console.print()

        success_panel = Panel(
            f"[bold green]Patching Complete![/bold green]\n\n"
            f"Raid: [cyan]{raid_index}[/cyan]\n"
            f"Patches applied: [cyan]{len(result['offsets'])}[/cyan]\n\n"
            f"[bold]Launch:[/bold] [cyan]{shortcut_name}[/cyan]\n"
            f"[dim]Located in: {escape(str(game_root))}[/dim]",
            box=box.DOUBLE,
            border_style="green",
            title="Success"
        )
        self.console.print(success_panel)
        self.console.print()
        
        # Ask if user wants to open the folder
        if Confirm.ask("Open folder where shortcut is located?", default=True):
            try:
                import os
                os.startfile(shortcut_path.parent)
            except Exception as e:
                logger.warning(f"Could not open folder: {e}")

    def execute_cleanup_workflow(self, game_info: Dict):
        """
        Execute cleanup workflow to remove all modifications.

        Args:
            game_info: Dictionary with game paths
        """
        paths = game_info['paths']
        game_root = game_info['game_root']

        # Confirm cleanup
        self.console.print()
        self.console.print("[yellow]This will remove all modifications made by this program:[/yellow]")
        self.console.print("  • Patched executable (RED-Win64-Shipping-eac-nop-loaded.exe)")
        self.console.print("  • All raid shortcuts (in game folder)")
        self.console.print("  • Application logs directory (~/.dbfz_raid_enabler)")
        self.console.print()
        self.console.print("[dim]Note: Original game files are never modified[/dim]")
        self.console.print()

        if not Confirm.ask("Are you sure you want to cleanup?", default=False):
            self.console.print()  # blank line for visual separation
            self.console.print("[yellow]Operation cancelled.[/yellow]")
            self.console.print()
            # Return False to indicate the user cancelled and wants to go back to the menu
            return False

        self.console.print()

        # Execute cleanup with transient spinner
        try:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console, transient=True) as progress:
                task = progress.add_task("Preparing cleanup...", total=None)

                # Provide a simple callback so `cleanup_all` can update the progress message
                def _update(msg: str):
                    try:
                        progress.update(task, description=msg)
                    except Exception:
                        pass

                # Pass the callback into cleanup_all so it can report detailed status
                result = self.backup_manager.cleanup_all(
                    paths['patched_exe'],
                    game_root,
                    progress_callback=_update
                )

                progress.update(task, description="Finalizing...", completed=True)
                try:
                    progress.refresh()
                except Exception:
                    pass

            # Show results
            items_removed = []
            if result['patched_exe_removed']:
                items_removed.append("Patched executable")
                self.console.print("[green]✓ Patched executable removed[/green]")
            else:
                self.console.print("[dim]• Patched executable not found[/dim]")

            shortcuts_count = result['shortcuts_removed']
            if shortcuts_count > 0:
                items_removed.append(f"{shortcuts_count} raid shortcut(s)")
                self.console.print(f"[green]✓ {shortcuts_count} raid shortcut(s) removed[/green]")
            else:
                self.console.print("[dim]• No raid shortcuts found[/dim]")

            # Logs directory removal
            if result.get('logs_removed'):
                items_removed.append("Application logs directory")
                self.console.print("[green]✓ Application logs directory removed[/green]")
            else:
                self.console.print("[dim]• Logs directory not found or not removed[/dim]")

            # Show errors if any
            if result['errors']:
                self.console.print()
                self.console.print("[yellow]Errors encountered:[/yellow]")
                for error in result['errors']:
                    self.console.print(f"  [yellow]• {error}[/yellow]")

                # Failure panel - treat cleanup as failed
                self.console.print()
                failure_panel = Panel(
                    f"[bold red]Cleanup failed[/bold red]\n\n"
                    f"Removed (partial):\n" +
                    "\n".join(f"  • {item}" for item in items_removed) + "\n\n"
                    f"[dim]Original game files may have been partially modified. Please inspect the errors above and restore files manually if needed.[/dim]",
                    box=box.DOUBLE,
                    border_style="red",
                    title="Failure"
                )
                self.console.print(failure_panel)
                self.console.print()
                self.console.print("[dim]Press Enter to exit...[/dim]")
                input()
                # Return True to indicate cleanup ran (even if it failed)
                return True

            # Success message
            self.console.print()
            if items_removed:
                cleanup_panel = Panel(
                    f"[bold green]Cleanup Complete![/bold green]\n\n"
                    f"Removed:\n" +
                    "\n".join(f"  • {item}" for item in items_removed) + "\n\n"
                    f"[dim]Original game files remain untouched[/dim]\n"
                    f"[dim]To reinstall EAC, run \"C:\\Program Files (x86)\\Steam\\steamapps\\common\\DRAGON BALL FighterZ\\EasyAntiCheat\\EasyAntiCheat_Setup.exe\"[/dim]",
                    box=box.DOUBLE,
                    border_style="green",
                    title="Success"
                )
            else:
                cleanup_panel = Panel(
                    f"[bold yellow]Nothing to Clean[/bold yellow]\n\n"
                    f"No modifications found\n"
                    f"[dim]Game files are already clean[/dim]",
                    box=box.ROUNDED,
                    border_style="yellow",
                    title="Info"
                )

            self.console.print(cleanup_panel)
            self.console.print()
            self.console.print("[dim]Press Enter to exit...[/dim]")
            input()
            # Return True to indicate cleanup ran (success)
            return True

        except Exception as e:
            # If a BackupError occurred it is already logged; show user-friendly failure
            self.console.print()
            self.console.print(f"[red]Cleanup failed: {e}[/red]")
            logger.exception("Cleanup error")
            # Return True to indicate cleanup attempted (exception occurred)
            return True

    def execute_logs_cleanup(self):
        """
        Clean up only the application logs directory.
        Used when game path is not available.
        """
        import shutil

        log_dir = Path.home() / ".dbfz_raid_enabler"

        self.console.print()
        self.console.print("[yellow]This will remove application logs:[/yellow]")
        self.console.print(f"  • {log_dir}")
        self.console.print()

        if not Confirm.ask("Are you sure?", default=False):
            self.console.print("\n[yellow]Operation cancelled.[/yellow]\n")
            return

        try:
            if log_dir.exists():
                # Close log file handlers before deleting
                for handler in logger.handlers[:]:
                    try:
                        base_filename = getattr(handler, 'baseFilename', None)
                        if base_filename:
                            handler_path = Path(base_filename).resolve()
                            log_dir_resolved = log_dir.resolve()
                            if log_dir_resolved == handler_path or log_dir_resolved in handler_path.parents:
                                handler.flush()
                                handler.close()
                                logger.removeHandler(handler)
                    except Exception:
                        pass

                shutil.rmtree(log_dir)
                self.console.print("[green]✓ Logs directory removed[/green]")
                self.console.print()
                self.console.print("[dim]Press Enter to exit...[/dim]")
                input()
                sys.exit(0)
            else:
                self.console.print("[dim]• Logs directory not found[/dim]")
        except Exception as e:
            self.console.print(f"[red]Failed to remove logs: {e}[/red]")

        self.console.print()

    # -------------------------------------------------------------------------
    # Custom raid
    # -------------------------------------------------------------------------

    def show_custom_raid_menu(self, game_info) -> bool:
        """
        Show custom raid sub-menu (create or load).

        Returns:
            False to return to main menu, None/True otherwise
        """
        self.console.print()
        self.console.print(Panel(
            "[bold cyan]Custom Raids[/bold cyan]\n"
            "[dim]Build your own raid and share it with friends[/dim]",
            box=box.ROUNDED,
            border_style="cyan"
        ))
        self.console.print()
        self.console.print("  [cyan]1[/cyan]  Create a new custom raid")
        self.console.print("  [cyan]2[/cyan]  Load a saved custom raid")
        self.console.print("  [cyan]b[/cyan]  Back")
        self.console.print()

        while True:
            try:
                choice = Prompt.ask("Select an option", console=self.console).strip().lower()
                if choice == '1':
                    self.create_custom_raid_wizard()
                    return False
                elif choice == '2':
                    return self.load_custom_raid_workflow(game_info)
                elif choice == 'b':
                    return False
                else:
                    self.console.print("[red]Invalid option.[/red]")
            except KeyboardInterrupt:
                self.console.print()
                return False

    def _show_character_table(self):
        """Display a compact reference table of all character codes."""
        table = Table(
            title="Character Codes",
            show_header=True,
            header_style="bold magenta",
            box=box.SIMPLE,
        )
        table.add_column("Code", style="cyan", width=6)
        table.add_column("Name", width=24)
        table.add_column("Code", style="cyan", width=6)
        table.add_column("Name", width=24)

        chars = [(k, v) for k, v in CHARACTER_CODES.items() if k != "AAA"]
        chars.sort(key=lambda x: x[1])

        for i in range(0, len(chars), 2):
            left = chars[i]
            right = chars[i + 1] if i + 1 < len(chars) else ("", "")
            table.add_row(left[0], left[1], right[0], right[1])

        self.console.print(table)
        self.console.print()

    def _prompt_character(self, label: str) -> str:
        """Prompt for a valid 3-letter character code."""
        while True:
            try:
                code = Prompt.ask(f"  {label}", console=self.console).strip().upper()
                if len(code) == 3 and code.isalpha():
                    name = CHARACTER_CODES.get(code, None)
                    if name:
                        self.console.print(f"  [dim]→ {name}[/dim]")
                    else:
                        self.console.print(f"  [yellow]Unknown code '{code}' — will be used as-is[/yellow]")
                    return code
                else:
                    self.console.print("  [red]Enter a 3-letter code (e.g. GKS)[/red]")
            except KeyboardInterrupt:
                self.console.print()
                return ""

    def create_custom_raid_wizard(self) -> Optional[CustomRaid]:
        """
        Interactive wizard to build a custom raid and save it as JSON.

        Returns:
            Saved CustomRaid, or None if cancelled
        """
        self.console.print()
        self.console.print("[bold]Create Custom Raid[/bold]")
        self.console.print("[dim]Press Ctrl+C at any time to cancel[/dim]")
        self.console.print()

        try:
            name = Prompt.ask("Raid name", console=self.console).strip()
            if not name:
                return None

            level_str = Prompt.ask("Default level for all battles", default="70", console=self.console).strip()
            try:
                default_level = max(1, min(100, int(level_str)))
            except ValueError:
                default_level = 70

            self.console.print()
            self._show_character_table()

            battles = []
            for i in range(7):
                self.console.print(f"[bold cyan]Battle {i + 1} of 7[/bold cyan]")

                char1 = self._prompt_character("Boss (Char1)")
                if not char1:
                    return None
                char2 = self._prompt_character("Support (Char2)")
                if not char2:
                    return None
                char3 = self._prompt_character("Support (Char3)")
                if not char3:
                    return None

                level_str = Prompt.ask(f"  Level", default=str(default_level), console=self.console)
                try:
                    level = max(1, min(100, int(level_str)))
                except ValueError:
                    level = default_level

                battles.append(RaidBattle(
                    battle_no=i,
                    char1=char1,
                    char2=char2,
                    char3=char3,
                    level=level,
                    skill_num=_DEFAULT_SKILL_NUM,
                    background=_DEFAULT_BACKGROUNDS[i],
                    bgm=_DEFAULT_BGM,
                ))
                self.console.print()

            raid = CustomRaid(name=name, battles=battles)
            saved_path = raid.save()

            self.console.print(Panel(
                f"[bold green]Raid saved![/bold green]\n\n"
                f"[white]{name}[/white]\n"
                f"[dim]{saved_path}[/dim]\n\n"
                f"Share the JSON file with friends — they can load it from the custom raid menu.",
                box=box.ROUNDED,
                border_style="green",
                title="Success"
            ))
            self.console.print()
            self.console.print("[dim]Press Enter to continue...[/dim]")
            input()
            return raid

        except KeyboardInterrupt:
            self.console.print()
            self.console.print("[yellow]Cancelled.[/yellow]")
            return None

    def load_custom_raid_workflow(self, game_info) -> bool:
        """
        Load a saved custom raid JSON and apply it to the game.

        Returns:
            False to return to menu
        """
        saved = list_saved_raids()

        # Also scan next to the patcher executable for dropped-in JSONs
        import sys
        exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent.parent
        for f in sorted(exe_dir.glob("*.json")):
            if f not in saved:
                saved.append(f)

        if not saved:
            self.console.print()
            self.console.print(
                f"[yellow]No custom raids found.[/yellow]\n"
                f"[dim]Place .json files in:[/dim]\n"
                f"[dim]  {CUSTOM_RAIDS_DIR}[/dim]\n"
                f"[dim]  or next to the patcher executable[/dim]"
            )
            self.console.print()
            self.console.print("[dim]Press Enter to continue...[/dim]")
            input()
            return False

        self.console.print()
        self.console.print("[bold]Load Custom Raid[/bold]")
        self.console.print()

        for i, path in enumerate(saved, 1):
            try:
                raid = CustomRaid.load(path)
                status = f"{len(raid.battles)} battles" if raid.is_complete() else "[yellow]incomplete[/yellow]"
                self.console.print(f"  [cyan]{i}[/cyan]  {escape(raid.name)} [dim]({status})[/dim]")
            except Exception:
                self.console.print(f"  [cyan]{i}[/cyan]  [dim]{path.name} (unreadable)[/dim]")

        self.console.print()

        try:
            choice = Prompt.ask("Select a raid (or 'b' to go back)", console=self.console).strip().lower()
            if choice == 'b':
                return False

            idx = int(choice) - 1
            if not 0 <= idx < len(saved):
                self.console.print("[red]Invalid selection.[/red]")
                return False

            raid = CustomRaid.load(saved[idx])

            if not raid.is_complete():
                self.console.print("[red]This raid is incomplete (needs 7 battles).[/red]")
                return False

        except (ValueError, KeyboardInterrupt):
            return False

        self.console.print()
        self.console.print(f"[bold]Loading:[/bold] {escape(raid.name)}")
        self.console.print(f"[dim]This will overwrite raid slot {CUSTOM_RAID_SLOT} in the pak.[/dim]")
        self.console.print()
        if not Confirm.ask("Continue?", default=True):
            return False

        pak_path = game_info['game_root'] / "RED" / "Content" / "Paks" / "pakchunk0-WindowsNoEditor.pak"
        aes_key = self._get_aes_key_with_fallback(pak_path)
        if aes_key is None:
            return False

        paths = game_info['paths']
        game_root = game_info['game_root']
        shortcut_name = f"DBFZ Raid {CUSTOM_RAID_SLOT}.lnk"
        shortcut_path = game_root / shortcut_name

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console, transient=True) as progress:
            task = progress.add_task("Loading custom raid...", total=4)

            progress.update(task, description="Backing up pak file...")
            from core.pak_manager import PakManager
            pak = PakManager(game_root, aes_key)
            try:
                pak.backup_pak()
            except PakError as e:
                self.console.print(f"[red]Failed to back up pak: {e}[/red]")
                return False
            progress.advance(task)

            progress.update(task, description="Injecting custom raid into pak...")
            try:
                pak.apply_custom_raid(raid.battles, CUSTOM_RAID_SLOT)
            except PakError as e:
                self.console.print(f"[red]Failed to inject raid into pak: {e}[/red]")
                return False
            progress.advance(task)

            progress.update(task, description="Patching executable...")
            try:
                self.backup_manager.verify_clean_exe(paths['clean_exe'])
                patched_exe = self.backup_manager.create_or_update_patched_exe(paths['clean_exe'], paths['patched_exe'])
                result = self.patcher.patch_executable(patched_exe, CUSTOM_RAID_SLOT)
                if not result['success']:
                    self.console.print(f"[red]Executable patch failed: {result['errors']}[/red]")
                    return False
            except Exception as e:
                self.console.print(f"[red]Failed to patch executable: {e}[/red]")
                return False
            progress.advance(task)

            progress.update(task, description="Creating shortcut...")
            try:
                for old in game_root.glob("DBFZ Raid *.lnk"):
                    try:
                        old.unlink()
                    except Exception:
                        pass
                self.shortcut_manager.create_shortcut(
                    paths['patched_exe'],
                    shortcut_path,
                    raid.name,
                )
            except Exception as e:
                logger.warning(f"Shortcut creation failed (non-critical): {e}")
            progress.advance(task)

        self.console.print()
        self.console.print(Panel(
            f"[bold green]{escape(raid.name)} loaded![/bold green]\n\n"
            f"[dim]Raid slot {CUSTOM_RAID_SLOT} is patched and active.[/dim]\n"
            f"[dim]Launch via [bold]{escape(shortcut_name)}[/bold] in your game folder.[/dim]",
            box=box.ROUNDED,
            border_style="green",
            title="Done"
        ))
        self.console.print()
        self.console.print("[dim]Press Enter to exit...[/dim]")
        input()
        return True

    def _get_aes_key_with_fallback(self, pak_path: Path) -> Optional[bytes]:
        """
        Return AES key, prompting the user if the pak file is not found or invalid.

        Returns:
            Key bytes, or None if user cancelled
        """
        try:
            return get_aes_key(pak_path)
        except AESKeyError as e:
            self.console.print()
            self.console.print(f"[yellow]{e}[/yellow]")
            self.console.print("[dim]If the pak file moved, enter its path or press 'b' to cancel.[/dim]")
            self.console.print()

            while True:
                try:
                    key_str = Prompt.ask("Enter AES key (or 'b' to cancel)", console=self.console).strip()
                    if key_str.lower() == 'b':
                        return None
                    return validate_user_key(key_str, pak_path)
                except AESKeyError as ve:
                    self.console.print(f"[red]{ve}[/red]")
                except KeyboardInterrupt:
                    self.console.print()
                    return None
