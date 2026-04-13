# -*- mode: python ; coding: utf-8 -*-
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


projectRoot = os.path.abspath(".")
modelDir = os.path.join(projectRoot, "model")
isMacOS = sys.platform == "darwin"
bundledModelFiles = [
    "colorization_deploy_v2.prototxt",
    "pts_in_hull.npy",
]

datas = collect_data_files("dearpygui")
datas += collect_data_files("dearpygui_ext")
if os.path.isdir(modelDir):
    for modelFileName in bundledModelFiles:
        modelFilePath = os.path.join(modelDir, modelFileName)
        if os.path.exists(modelFilePath):
            datas.append((modelFilePath, "model"))

binaries = collect_dynamic_libs("dearpygui")
binaries += collect_dynamic_libs("cv2")

hiddenimports = collect_submodules("dearpygui_ext")


a = Analysis(
    ["main.py"],
    pathex=[projectRoot],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cnn-colorizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cnn-colorizer",
)

if isMacOS:
    app = BUNDLE(
        coll,
        name="cnn-colorizer.app",
        icon=None,
        bundle_identifier="com.redzep.cnn-colorizer",
        version="1.0.0",
        info_plist={
            "NSPrincipalClass": "NSApplication",
            "CFBundleDisplayName": "cnn-colorizer",
            "CFBundleName": "cnn-colorizer",
        },
    )
