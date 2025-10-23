from __future__ import annotations
import os
import sys
import asyncio
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QGuiApplication
import qasync

try:
    from qt_material import apply_stylesheet
except Exception:
    apply_stylesheet = None

from config_utils import ConfigManager
from download_panel import DownloadPanel
from config_panel import ConfigPanel

APP_TITLE = "StreamRIP-GUI"
GUI_VERSION = "streamrip-gui v0.1.0"
BASE_DIR = Path(__file__).resolve().parent


def main():
    app = QtWidgets.QApplication(sys.argv)

    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion("1.0")
    app.setOrganizationName("streamrip_gui")

    QGuiApplication.setDesktopFileName("streamrip-gui")

    if apply_stylesheet:
        try:
            apply_stylesheet(app, theme="dark_teal.xml")
        except Exception:
            pass

    icon_paths = [
        BASE_DIR / "svg" / "logo_streamrip.svg",
        BASE_DIR / "icons" / "logo_streamrip.png",
    ]
    for p in icon_paths:
        if p.exists():
            app.setWindowIcon(QIcon(str(p)))
            break

    cfg_mgr = ConfigManager()

    win = QtWidgets.QMainWindow()
    win.setWindowTitle(APP_TITLE)

    if icon_paths[0].exists():
        win.setWindowIcon(QIcon(str(icon_paths[0])))

    splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
    download = DownloadPanel(cfg_mgr, gui_version=GUI_VERSION)
    config = ConfigPanel(cfg_mgr)
    splitter.addWidget(download)
    splitter.addWidget(config)
    win.setCentralWidget(splitter)

    def init_sizes():
        w = max(1, splitter.width())
        splitter.setSizes([int(w * 0.60), int(w * 0.40)])

    QTimer.singleShot(0, init_sizes)

    win.resize(1280, 800)
    win.showMaximized()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
