# -*- mode: python ; coding: utf-8 -*-
# void_player.spec — OTERNOS PLAYER
# Edit this file directly instead of regenerating it via build.bat.

from PyInstaller.utils.hooks import collect_all, collect_submodules
import os

# ── Data files ───────────────────────────────────────────────────────
datas = [
    ('boot.mp3',                       '.'),
    ('oternos\\boot_screen.html',      'oternos'),
    ('oternos\\init_screen.html',      'oternos'),
    ('oternos',                        'oternos'),
]

binaries = []

# ── Hidden imports ───────────────────────────────────────────────────
hiddenimports = [
    # Audio
    'pygame',
    'pygame.mixer',
    'soundfile',
    'sounddevice',

    # Metadata
    'mutagen',
    'mutagen.mp3',
    'mutagen.id3',
    'mutagen.flac',
    'mutagen.oggvorbis',
    'mutagen.mp4',
    'mutagen.aac',
    'mutagen.asf',
    'mutagen.wave',

    # DSP
    'scipy',
    'scipy.signal',
    'scipy.signal._max_len_seq_inner',
    'scipy.signal._upfirdn_apply',
    'numpy',
    'numpy.core',
    'numpy.lib',

    # Image / UI
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',

    # Web / streaming
    'webview',
    'webview.platforms.winforms',
    'urllib.request',
    'urllib.parse',

    # Oternos internals
    'oternos.stream_cards',
    'oternos.mixer',
    'oternos.analyzers',
    'oternos.mixins',
    'oternos.mixins.soundcloud_mixin',
    'oternos.mixins.youtube_mixin',
    'oternos.mixins.spotify_mixin',
    'oternos.mixins.deezer_mixin',
    'oternos.mixins.archive_mixin',
    'oternos.mixins.bandcamp_mixin',
    'oternos.mixins.streaming_mixin',
    'oternos.mixins.visualizer_mixin',
    'oternos.patches',

    # Misc stdlib that PyInstaller sometimes misses
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.ttk',
    'json',
    'threading',
    'pathlib',
    'tempfile',
    'subprocess',
    'winreg',
    'ctypes',
    'ctypes.wintypes',
]

# ── Collect everything from oternos package ──────────────────────────
tmp_ret = collect_all('oternos')
datas         += tmp_ret[0]
binaries      += tmp_ret[1]
hiddenimports += tmp_ret[2]

# ── Modules to exclude (reduces build size significantly) ────────────
excludes = [
    'matplotlib',
    'matplotlib.pyplot',
    'IPython',
    'ipykernel',
    'notebook',
    'pytest',
    'unittest',
    'setuptools',
    'pip',
    'pkg_resources',
    'docutils',
    'sphinx',
    'pydoc',
    'xmlrpc',
    'ftplib',
    'imaplib',
    'poplib',
    'smtplib',
    'telnetlib',
    'turtle',
    'tkinter.test',
    'lib2to3',
    'test',
    'tests',
    '_pytest',
    'wx',
    'gi',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
]

# ── Analysis ─────────────────────────────────────────────────────────
a = Analysis(
    ['oternos\\__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,          # bytecode optimisation (strips docstrings → smaller)
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='void_player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # ── Uncomment the icon line once you have an .ico file ──────────
    # icon='oternos\\icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        # Don't UPX compress these — it breaks them
        'vcruntime*.dll',
        'msvcp*.dll',
        'python*.dll',
        'pygame*',
    ],
    name='void_player',
)
