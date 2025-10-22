# main.spec
from PyInstaller.utils.hooks import collect_all
import os

# Try to collect all resources from streamrip package (config templates, etc.)
sr_datas, sr_binaries, sr_hiddenimports = collect_all('streamrip')

# If you use PyQt6 or PySide6, collecting their plugins helps avoid missing DLLs on Windows
qt_module = os.getenv("QT_MODULE", "PySide6")
qt_datas, qt_bins, qt_hidden = [], [], []
try:
    qd, qb, qh = collect_all(qt_module)
    qt_datas, qt_bins, qt_hidden = qd, qb, qh
except Exception:
    pass

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=sr_binaries + qt_bins,
    datas=sr_datas + qt_datas,
    hiddenimports=sr_hiddenimports + qt_hidden + [
        # common extras that PyInstaller sometimes misses
        'pkg_resources.py2_warn',
        'mutagen',
        'requests',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='streamrip-gui',
    console=False,        # set True to see console output
    icon='assets/app.ico' # optional, add your .ico here or remove this line
)