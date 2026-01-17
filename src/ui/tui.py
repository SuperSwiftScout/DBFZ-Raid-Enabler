"""Terminal UI for DBFZ Raid Enabler."""

import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from pathlib import Path
from typing import Optional, Dict, Union

from core.patcher import BinaryPatcher
from core.raid_data import get_all_raids, get_raid_name
from steam.game_locator import GameLocator
from file_manager.backup import BackupManager
from file_manager.shortcut import ShortcutManager
from utils.errors import (
    DBFZRaidError,
    SteamNotFoundError,
    GameNotFoundError
)
from utils.logger import logger


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
                self.console.print("\n[red]Cannot proceed without game installation.[/red]")
                self.console.print("[dim]Press Enter to exit...[/dim]")
                input()
                return

            # Step 2: Check current patch status
            current_raid = self.check_current_patch(game_info)

            # Step 3: Show raid selection menu
            selection = self.show_raid_menu(current_raid)
            if not selection:
                self.console.print("\n[yellow]Operation cancelled.[/yellow]")
                return

            # Step 4: Execute workflow based on selection
            if selection == 'cleanup':
                self.execute_cleanup_workflow(game_info)
            elif isinstance(selection, int):
                self.execute_patch_workflow(game_info, selection, current_raid)

        except KeyboardInterrupt:
            self.console.print("\n\n[yellow]Operation cancelled by user.[/yellow]")
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
            "[dim]Enable raid battles for Dragon Ball FighterZ[/dim]\n"
            "[dim]Python Edition - Automated Patching System[/dim]\n"
            "[dim]Version: 1.0.0[/dim]",
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
            console=self.console
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

                self.console.print(f"[yellow]Game not found in Steam libraries. Checking common paths...[/yellow]")
                self.console.print()

                # Try common paths as fallback
                game_root = self.check_common_paths_with_output()

                if game_root and self.game_locator.validate_installation(game_root):
                    paths = self.game_locator.get_file_paths(game_root)
                    self.console.print()
                    self.console.print(f"[green]✓ Found DBFZ at:[/green] [cyan]{game_root}[/cyan]")
                    self.console.print()
                    return {'game_root': game_root, 'paths': paths}

                # If common paths also failed, show error and offer manual input
                self.console.print()
                self.console.print(f"[red]{e}[/red]")
                self.console.print("[yellow]Common installation paths also checked with no success.[/yellow]")
                # Offer manual path input as final fallback
                return self.manual_game_path_input()

            progress.update(task, description="Game found!", completed=True)

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

                # Show what we're checking
                self.console.print(f"[dim]Checking: {exe_path}[/dim]")

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
                    self.console.print(f"  [dim]→ Not found[/dim]")

                    # If this is the first path (most likely), check what's in the directory
                    if base == base_paths[0][0]:  # First path, first case
                        parent_dir = os.path.dirname(exe_path_str)
                        if os.path.exists(parent_dir):
                            try:
                                files = os.listdir(parent_dir)
                                logger.info(f"  Directory exists. Files in {parent_dir}:")
                                logger.info(f"    {files}")
                                self.console.print(f"    [yellow]Win64 directory exists but executable not found![/yellow]")
                                self.console.print(f"    [yellow]This usually means game files are corrupted or modified.[/yellow]")
                                self.console.print(f"    [cyan]→ Fix: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity[/cyan]")
                            except Exception as e:
                                logger.error(f"  Could not list directory: {e}")
                        else:
                            # Check if game root exists
                            game_root_str = str(game_path)
                            if os.path.exists(game_root_str):
                                logger.info(f"  Game root exists but Win64 directory missing: {game_root_str}")
                                self.console.print(f"    [yellow]Game folder exists but installation is incomplete![/yellow]")
                                self.console.print(f"    [cyan]→ Fix: Right-click DBFZ in Steam → Properties → Installed Files → Verify integrity[/cyan]")
                            else:
                                logger.info(f"  Game not installed at: {game_root_str}")

        return None

    def manual_game_path_input(self) -> Optional[Dict]:
        """
        Prompt user to manually enter game path when automatic detection fails.

        Returns:
            Dictionary with game_root and paths, or None if cancelled/invalid
        """
        self.console.print()
        self.console.print("[yellow]Automatic detection failed. You can manually enter the game path.[/yellow]")
        self.console.print("[dim]Example: C:\\Program Files (x86)\\Steam\\steamapps\\common\\DRAGON BALL FighterZ[/dim]")
        self.console.print()

        while True:
            try:
                user_input = Prompt.ask(
                    "Enter game path (or 'q' to quit)",
                    console=self.console
                )

                if user_input.lower() == 'q':
                    return None

                # Clean up the input path
                game_path = Path(user_input.strip().strip('"').strip("'"))

                # Validate the path
                if not game_path.exists():
                    self.console.print(f"[red]Path does not exist: {game_path}[/red]")
                    continue

                if not game_path.is_dir():
                    self.console.print(f"[red]Path is not a directory: {game_path}[/red]")
                    continue

                # Validate it's a valid DBFZ installation
                if not self.game_locator.validate_installation(game_path):
                    self.console.print(f"[red]Invalid DBFZ installation at: {game_path}[/red]")
                    self.console.print("[dim]Make sure you're pointing to the 'DRAGON BALL FighterZ' folder[/dim]")
                    continue

                # Success - generate paths
                paths = self.game_locator.get_file_paths(game_path)
                self.console.print(f"[green]✓ Found DBFZ at:[/green] [cyan]{game_path}[/cyan]")
                self.console.print()

                return {'game_root': game_path, 'paths': paths}

            except KeyboardInterrupt:
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
        current_raid = self.backup_manager.detect_current_patch(paths['patched_exe'])

        if current_raid:
            raid_name = get_raid_name(current_raid)
            self.console.print(
                f"[yellow]Current patch:[/yellow] Raid {current_raid} - {raid_name}"
            )
            self.console.print()

        return current_raid

    def show_raid_menu(self, current_raid: Optional[int]) -> Union[int, str, None]:
        """
        Display interactive raid selection menu.

        Args:
            current_raid: Currently patched raid index (or None)

        Returns:
            Selected raid index (int), 'cleanup' for cleanup, or None if cancelled
        """
        raids = get_all_raids()

        # Create table
        table = Table(
            title="Select a Raid",
            caption="[dim]Note: Only one raid can be active at a time[/dim]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Index", style="cyan", justify="right", width=6)
        table.add_column("Raid Boss", style="white", no_wrap=False)
        table.add_column("Status", style="white", width=10)

        # Add rows
        for idx, name in raids:
            if idx == current_raid:
                status = "[bold green]ACTIVE[/bold green]"
            else:
                status = "[dim]INACTIVE[/dim]"
            table.add_row(str(idx), name, status)

        self.console.print(table)
        self.console.print()

        # Prompt for selection
        while True:
            try:
                default_str = f"Current raid: {current_raid}" if current_raid else "No current raid"
                choice = Prompt.ask(
                    "Enter raid number (1-38), 'c' to cleanup, or 'q' to quit",
                    default=default_str,
                    console=self.console
                )

                choice_lower = choice.lower()

                if choice_lower == 'q':
                    return None

                if choice_lower == 'c':
                    return 'cleanup'

                raid_idx = int(choice)
                if 1 <= raid_idx <= 38:
                    return raid_idx
                else:
                    self.console.print("[red]Invalid raid number. Must be 1-38.[/red]")

            except ValueError:
                self.console.print("[red]Invalid input. Enter a number, 'c' for cleanup, or 'q'.[/red]")
            except KeyboardInterrupt:
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
        raid_name = get_raid_name(raid_index)

        # Check if already patched
        if current_raid == raid_index:
            self.console.print(
                f"\n[yellow]Raid {raid_index} ({raid_name}) is already active![/yellow]"
            )
            if not Confirm.ask("Do you want to re-patch anyway?", default=False):
                return

        self.console.print(f"\n[bold]Patching for: {raid_name}[/bold]\n")

        with Progress(console=self.console) as progress:
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

            # Generate shortcut filename with raid name
            shortcut_name = f"DBFZ Raid {raid_index} - {raid_name}.lnk"
            shortcut_path = game_root / shortcut_name

            try:
                self.shortcut_manager.create_shortcut(
                    paths['patched_exe'],
                    shortcut_path,
                    raid_name
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
            f"Run: [cyan]{game_root}\\EasyAntiCheat\\EasyAntiCheat_Setup.exe[/cyan]\n"
            f"Then click 'Uninstall'\n\n"
            f"[dim]Note: This is required to bypass anti-cheat for raids, otherwise the patch may not function correctly and leads to Desync issues.[/dim]",
            box=box.ROUNDED,
            border_style="yellow",
            title="Action May Be Required"
        )
        self.console.print(eac_panel)
        self.console.print()

        success_panel = Panel(
            f"[bold green]Patching Complete![/bold green]\n\n"
            f"Raid: [cyan]{raid_name}[/cyan]\n"
            f"Patch Offsets:\n"
            f"  • Get Raid:    0x{result['offsets'].get('get_raid', 0):X}\n"
            f"  • Set Raid:    0x{result['offsets'].get('set_raid', 0):X}\n"
            f"  • Raid Status: 0x{result['offsets'].get('raid_status', 0):X}\n\n"
            f"[bold]Launch via shortcut:[/bold] [cyan]{shortcut_name}[/cyan]\n"
            f"[dim]Located in: {game_root}[/dim]",
            box=box.DOUBLE,
            border_style="green",
            title="Success"
        )
        self.console.print(success_panel)
        self.console.print()
        
        # Ask if user wants to open the folder
        if Confirm.ask("Open folder where shortcut is located?", default=True):
            try:
                import subprocess
                subprocess.run(['explorer', '/select,', str(shortcut_path)])
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
        self.console.print()
        self.console.print("[dim]Note: Original game files are never modified[/dim]")
        self.console.print()

        if not Confirm.ask("Are you sure you want to cleanup?", default=False):
            self.console.print("[yellow]Cleanup cancelled.[/yellow]")
            return

        self.console.print()
        self.console.print("[bold]Cleaning up...[/bold]\n")

        # Execute cleanup
        try:
            result = self.backup_manager.cleanup_all(
                paths['patched_exe'],
                game_root
            )

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

            # Show errors if any
            if result['errors']:
                self.console.print()
                self.console.print("[yellow]Errors encountered:[/yellow]")
                for error in result['errors']:
                    self.console.print(f"  [yellow]• {error}[/yellow]")

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

        except Exception as e:
            self.console.print()
            self.console.print(f"[red]Cleanup failed: {e}[/red]")
            logger.exception("Cleanup error")
