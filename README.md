# DBFZ Raid Enabler

DBFZ Raid Enabler patches the Dragon Ball FighterZ executable to enable raid events locally, allowing you to access raid battles again. Raids can be played with friends online (requires 3 players). The tool features an interactive terminal interface, automatic game detection via Steam, and creates shortcuts in your game folder for easy access.

### [DOWNLOAD](../../releases)

## Read Before You Play

To avoid desync issues during online raid play, **all players must be on the same local network (LAN)**. If you're playing with friends over the internet, use a VPN tunneling solution to simulate a LAN connection:

- **Radmin VPN**
- **Hamachi**
- **Tailscale**

Without LAN or VPN tunneling, you will likely experience severe desynchronization that makes raids unplayable.

## Table of Contents

- [Read Before You Play](#read-before-you-play)
- [Credits](#credits)
- [Features](#features)
- [Requirements](#requirements)
- [Compatibility](#compatibility)
- [Installation](#installation)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [How It Works](#how-it-works)
- [How Patching Works](#how-patching-works)
- [Logs](#logs)
- [Building](#building)
- [Project Structure](#project-structure)
- [Disclaimer](#disclaimer)

## Credits

This project is a Python reimplementation of the original C# tool with added features and improved user experience.

**Original Patching Logic**: [Gneiss64/DBFZRaidEnabler](https://github.com/Gneiss64/DBFZRaidEnabler)

The pattern matching and binary patching techniques are based on Gneiss64's original work.

## Features

- **Automatic Game Detection**: Finds your DBFZ installation through Steam
- **Binary Patching**: Patches the game executable to enable any raid index
- **Non-Destructive**: Creates a separate patched executable, leaving the original untouched
- **Raid Selection**: Choose from a list of available raid battles
- **Shortcut Creation**: Creates convenient shortcuts in your game folder to patched executables
- **Interactive TUI**: User-friendly terminal interface powered by Rich
- **Safe Patching**: Validates all operations and provides detailed logging

## Requirements

- Windows OS
- Dragon Ball FighterZ installed via Steam
- Python 3.13+ (for running from source)

## Compatibility

Currently tested and working with:
- **Game Version**: 4.17.2.0
- **Last Verified**: January 2026

## Installation

### Option 1: Pre-built Executable (Recommended)
1. Download the latest release from the [Releases](../../releases) page
2. Run `DBFZ-Raid-Enabler.exe`

### Option 2: From Source
1. Clone the repository:
   ```bash
   git clone https://github.com/SuperSwiftStalker/DBFZ-Raid-Enabler.git
   cd DBFZ-Raid-Enabler
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python src/main.py
   ```

## Usage

1. Launch the application
2. The tool will automatically locate your DBFZ installation
3. Select the raid battle you want to enable
4. Confirm the patching operation
5. Uninstall EAC (If not already uninstalled)
6. A shortcut will be created in your game folder for easy access
7. Launch the game and enjoy the raid battle!

## Troubleshooting

### Antivirus False Positives
Some antivirus software may flag the patched executable or `DBFZ_Raid_Enabler.exe` as suspicious:
- This is a common false positive for binary patching tools
- You may need to add an exception for these files in your antivirus software
- Alternatively, temporarily disable real-time protection while running the patcher
- The tool is open-source and can be reviewed for safety

### Desync Issues
If you're experiencing major desynchronization issues during online play:
- **Use LAN or VPN tunneling**: All players must be on the same local network. If playing over the internet, use VPN tunneling software like Radmin VPN, Hamachi, or ZeroTier
- Ensure EAC (Easy Anti-Cheat) is properly uninstalled
- Verify that **all players** are using the executable that was patched with this program
- All players must be on the same patched version to avoid desync

### Other Issues
If you encounter other problems:
1. Use the built-in cleanup feature in the program
   - **Note**: Only use cleanup if you've actually patched the game
2. Verify the integrity of game files through Steam:
   - Right-click Dragon Ball FighterZ in Steam
   - Select Properties → Installed Files → Verify integrity of game files
3. Re-run the patcher after verification

**Important**: Verifying game file integrity through Steam does **not** delete the files created by this program. That's why there's a built-in cleanup function to properly remove patched files when needed.

## How It Works

The patcher performs five binary modifications to the game executable:
- **Get Raid**: Patches the function that retrieves the current raid index
- **Set Raid**: Patches the function that sets the active raid
- **Raid Status**: Bypasses the online raid availability check
- **FCup Skip**: Prevents FCup popup that can cause softlocks
- **Partybattle Skip**: Prevents Partybattle popup that can cause softlocks

The core raid patterns are based on the original C# implementation, with additional patches to improve stability.

## How Patching Works

- The tool creates a copy of your original executable (`RED-Win64-Shipping-Raid.exe`)
- Your original `RED-Win64-Shipping.exe` is never modified and remains intact
- All patches are applied to the copy, keeping your game installation safe
- You can delete the patched executable anytime to return to vanilla gameplay

## Logs

The application creates detailed logs for troubleshooting purposes:
- **Location**: `%USERPROFILE%\.dbfz_raid_enabler\dbfz_raid.log`
- **Quick Access**: Press `Win + R`, type `%USERPROFILE%\.dbfz_raid_enabler`, and press Enter

## Building

To build a standalone executable:

```bash
pyinstaller pyinstaller.spec
```

The executable will be created in the `dist/` directory.

## Project Structure

```
src/
├── main.py                 # Entry point
├── core/
│   ├── patcher.py         # Binary patching engine
│   └── raid_data.py       # Raid battle definitions
├── file_manager/
│   ├── backup.py          # Backup management
│   └── shortcut.py        # Desktop shortcut creation
├── steam/
│   └── game_locator.py    # Steam game detection
├── ui/
│   ├── screens.py         # UI screen components
│   └── tui.py            # Terminal UI framework
└── utils/
    ├── errors.py          # Error definitions
    └── logger.py          # Logging utilities
```

## Disclaimer

This tool is for educational and preservation purposes. Use it responsibly and at your own risk. The developers are not responsible for any issues that may arise from using this tool.
