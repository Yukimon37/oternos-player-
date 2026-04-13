# -*- mode: python ; coding: utf-8 -*-
# oternos_qt.spec - OTERNOS Qt shell
# Builds the Phase 2 PySide6 shell beside the legacy void_player.exe.

from PyInstaller.utils.hooks import collect_submodules


datas = []
binaries = []

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtNetwork",
    "PySide6.QtWidgets",
    "oternos.core.app_state",
    "oternos.core.library",
    "oternos.core.runtime_commands",
    "oternos.core.runtime_state",
    "oternos.core.settings",
    "oternos.ui_qt",
    "oternos.ui_qt.shell",
]

hiddenimports += collect_submodules("oternos.core")
hiddenimports += collect_submodules("oternos.ui_qt")

excludes = [
    "IPython",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "_pytest",
    "docutils",
    "gi",
    "ipykernel",
    "lib2to3",
    "matplotlib",
    "matplotlib.pyplot",
    "notebook",
    "pkg_resources",
    "pydoc",
    "pytest",
    "setuptools",
    "sphinx",
    "test",
    "tests",
    "tkinter.test",
    "turtle",
    "unittest",
    "wx",
]

a = Analysis(
    ["oternos\\qt_main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="oternos_qt",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        "vcruntime*.dll",
        "msvcp*.dll",
        "python*.dll",
        "PySide6\\*.pyd",
        "Qt6*.dll",
    ],
    name="oternos_qt",
)
