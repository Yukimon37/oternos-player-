# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

# ── Collect oternos package ───────────────────────────────────────────────────
datas = [
    ('boot.mp3', '.'),
    # Copy entire oternos package including patches/ and mixins/ as raw .py files
    # so the runtime patch loader can read them from disk
    ('oternos', 'oternos'),
]
binaries = []
hiddenimports = [
    'pygame',
    'mutagen', 'mutagen.mp3', 'mutagen.id3', 'mutagen.flac',
    'mutagen.oggvorbis', 'mutagen.mp4',
    'soundfile',
    'scipy', 'scipy.signal',
    'numpy',
    # Mixin modules — must be explicit so PyInstaller doesn't miss them
    'oternos.mixins',
    'oternos.mixins.soundcloud_mixin',
    'oternos.mixins.youtube_mixin',
    'oternos.mixins.spotify_mixin',
    'oternos.mixins.visualizer_mixin',
    'oternos.mixins.deezer_mixin',
    'oternos.mixins.archive_mixin',
    'oternos.mixins.bandcamp_mixin',
    'oternos.mixins.streaming_mixin',
    # Patch modules
    'oternos.patches',
    # importlib.util needed by patch loader at runtime
    'importlib.util',
    'importlib.machinery',
]

tmp_ret = collect_all('oternos')
datas          += tmp_ret[0]
binaries       += tmp_ret[1]
hiddenimports  += tmp_ret[2]

a = Analysis(
    ['oternos\\__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='void_player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
