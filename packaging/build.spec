# packaging/build.spec (Example - Needs adjustments!)
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, copy_metadata, collect_submodules

# --- Adjust paths ---
# Assume spec file is in the 'packaging' directory, one level below project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec_dir = os.path.dirname(os.path.abspath(__file__))

block_cipher = None

# --- Data Files ---
# Collect necessary data files from libraries
datas = []
datas += collect_data_files('google.generativeai')
datas += collect_data_files('google.api_core') # Often needed for protobuf/grpc stuff
datas += collect_data_files('google.protobuf')
datas += collect_data_files('grpc')
datas += collect_data_files('pyperclip') # Sometimes needs data files
datas += collect_data_files('pynput')    # May need data depending on platform/backend
# datas += collect_data_files('mss') # Usually doesn't need data files

# Add application icon
icon_src_path = os.path.join(project_root, 'ui', 'icons', 'app_icon.png')
if os.path.exists(icon_src_path):
    datas += [(icon_src_path, os.path.join('ui', 'icons'))]
else:
     print(f"WARNING: Icon file not found at {icon_src_path}, not bundling icon image data.")


# --- Hidden Imports ---
# List modules that PyInstaller might miss
hiddenimports = [
    'pkg_resources.py2_warn', # Common requirement
    # Pynput backends (include specific ones needed for target platforms)
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    # 'pynput.keyboard._xorg', # For Linux/X11
    # 'pynput.mouse._xorg',
    # 'pynput.keyboard._darwin', # For macOS
    # 'pynput.mouse._darwin',
    # Google / gRPC / Protobuf related (collect_submodules might catch some)
    'google.ai',
    'google.api',
    'google.logging',
    'google.longrunning',
    'google.rpc',
    'google.type',
    'grpc._cython', # Cython parts of grpc
    # Potentially add PyQt6 plugins if needed, though often handled automatically
    # 'PyQt6.QtNetwork', # If network features used beyond basic requests
    # 'PyQt6.QtSvg', # If using SVG icons
]
# Use collect_submodules for broad coverage, can increase size
# hiddenimports += collect_submodules('google')
# hiddenimports += collect_submodules('grpc')

# --- Main Analysis ---
a = Analysis(
    [os.path.join(project_root, 'main.py')], # Path to main script from spec file location
    pathex=[project_root], # Add project root to Python path
    binaries=[],
    datas=datas, # Assign collected data files
    hiddenimports=hiddenimports, # Assign hidden imports
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- Executable ---
# Determine icon path based on OS
app_icon = None
icon_ico = os.path.join(project_root, 'ui', 'icons', 'app_icon.ico')
icon_icns = os.path.join(project_root, 'ui', 'icons', 'app_icon.icns')
if sys.platform == 'win32' and os.path.exists(icon_ico):
    app_icon = icon_ico
elif sys.platform == 'darwin' and os.path.exists(icon_icns):
    app_icon = icon_icns
elif os.path.exists(icon_src_path): # Fallback to png for Linux (may require desktop file)
     # PyInstaller doesn't directly use .png for Linux executable icon,
     # but having it referenced might be useful for packaging/scripts.
     # A .desktop file is the standard way on Linux.
     pass # No direct icon argument for Linux EXE


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeminiChatApp', # Executable name
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Set to False if UPX causes issues
    # console=False, # For GUI apps (no terminal window)
    windowed=True, # Preferred way for GUI apps
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon # Assign the OS-specific icon path
)

# --- Collect (For one-folder builds, not used in one-file) ---
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='GeminiChatApp_AppDir', # Directory name if building one-folder
# )

# --- macOS App Bundle (Optional, modify EXE/COLLECT if using) ---
# app = BUNDLE(
#     exe, # Or use 'coll' if building a folder first
#     name='GeminiChatApp.app',
#     icon=icon_icns,
#     bundle_identifier='com.yourappname.geminichat' # Replace with your identifier
#     # Info.plist settings can be added via 'info_plist' argument
# )
