# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for DBFZ Raid Enabler
Builds a single-file executable with all dependencies bundled.
"""

block_cipher = None

a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # Add any data files here if needed
        # ('icon.ico', '.'),
    ],
    hiddenimports=[
        'win32com.client',
        'win32com.gen_py',
        'win32com.shell',
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
    ],
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DBFZ_Raid_Enabler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for TUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',  # Uncomment if you have an icon
    version_info=None,  # Can add version info here
)
