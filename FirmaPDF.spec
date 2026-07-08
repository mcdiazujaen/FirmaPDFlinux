# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtNetwork', 'PySide6.QtDBus', 'PySide6.QtQml', 'PySide6.QtQuick',
        'PySide6.QtSvg', 'PySide6.QtMultimedia', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtDesigner', 'PySide6.Qt3D',
        'PySide6.QtBluetooth', 'PySide6.QtSensors', 'PySide6.QtPdf',
        'PySide6.QtOpenGL', 'PySide6.QtCharts', 'PySide6.QtGraphs',
        'PySide6.QtSpatialAudio'
    ],
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
    name='FirmaPDF_v1.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
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
