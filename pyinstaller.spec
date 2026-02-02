# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for DBFZ Raid Enabler
Builds a single-file executable with all dependencies bundled.
Cross-platform support for Windows and Linux.
"""

import sys
import os

block_cipher = None

# Platform detection
is_windows = sys.platform == 'win32'
is_linux = sys.platform.startswith('linux')

# Use forward slashes for paths (works on all platforms)
main_script = os.path.join('src', 'main.py')

# Platform-specific hidden imports
hiddenimports = [
    'vdf',
    'rich',
    'rich.console',
    'rich.table',
    'rich.panel',
    'rich.prompt',
    'rich.progress',
    'rich.box',
    'rich.text',
    # All our modules
    'ui',
    'ui.tui',
    'core',
    'core.patcher',
    'core.raid_data',
    'steam',
    'steam.detector',
    'steam.game_locator',
    'file_manager',
    'file_manager.backup',
    'file_manager.shortcut',
    'utils',
    'utils.logger',
    'utils.errors',
    'utils.platform',
]

# Add Windows-specific imports only on Windows
if is_windows:
    hiddenimports.extend([
        'win32com.client',
        'win32com.gen_py',
        'win32com.shell',
    ])

a = Analysis(
    [main_script],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Platform-specific executable name
if is_linux:
    exe_name = 'DBFZ_Raid_Enabler.bin'
else:
    exe_name = 'DBFZ_Raid_Enabler'

# Platform-specific EXE options
exe_kwargs = {
    'name': exe_name,
    'debug': False,
    'bootloader_ignore_signals': False,
    'strip': False,
    'upx': True,
    'upx_exclude': [],
    'runtime_tmpdir': None,
    'console': True,  # Keep console for TUI
    'disable_windowed_traceback': False,
    'argv_emulation': False,
    'target_arch': None,
    'codesign_identity': None,
    'entitlements_file': None,
}

# Add icon only on Windows
if is_windows and os.path.exists('icon.ico'):
    exe_kwargs['icon'] = 'icon.ico'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    **exe_kwargs,
)
