# main.spec
# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

# ---- Collect PySide6 runtime (plugins, imageformats, etc.) ----
qt_datas, qt_bins, qt_hidden = ([], [], [])
try:
    qd, qb, qh = collect_all("PySide6")
    qt_datas, qt_bins, qt_hidden = qd, qb, qh
except Exception:
    pass

# ---- Collect streamrip package and data ----
sr_datas, sr_bins, sr_hidden = ([], [], [])
try:
    sd, sb, sh = collect_all("streamrip")
    sr_datas, sr_bins, sr_hidden = sd, sb, sh
except Exception:
    pass

# Template config (ensure available at streamrip/config.toml inside the app)
template_src = "streamrip/config.toml"
if not os.path.exists(template_src):
    alt = "streamrip/src/config.toml"
    if os.path.exists(alt):
        template_src = alt

extra_datas = []
if os.path.exists(template_src):
    extra_datas.append((template_src, "streamrip"))

# App assets
extra_datas += [
    ("assets/logo_streamrip.ico", "assets"),
    ("assets/logo_streamrip.svg", "assets"),
]

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=sr_bins + qt_bins,
    datas=sr_datas + qt_datas + extra_datas,
    hiddenimports=list(set(sr_hidden + qt_hidden + [
        "mutagen",
        "requests",
        "PySide6.QtWidgets",   # make sure core widget module is in
    ])),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude PySide6 deploy helpers that trigger the 'project_lib' warning
    excludes=[
        "PySide6.scripts",
        "PySide6.scripts.*",
        "PySide6.scripts.deploy",
        "PySide6.scripts.deploy_lib",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="streamrip-gui",
    console=False,
    icon="assets/logo_streamrip.ico",
)
