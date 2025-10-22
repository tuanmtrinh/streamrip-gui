# download_panel.py
# Streamrip GUI – Download panel (URLs + Queue + internal status bar)
from __future__ import annotations

import asyncio
import logging
import pathlib
import re
from typing import List, Optional

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QUrl

try:
    # optional: qt-material theming (we only use DARK themes; no live palette changes)
    from qt_material import apply_stylesheet as _apply_theme
except Exception:  # pragma: no cover
    _apply_theme = None

from config_utils import ConfigManager


# ------------------------- helpers -------------------------

def infer_platform(url: str) -> str:
    u = url.lower()
    if "qobuz" in u:
        return "Qobuz"
    if "deezer" in u:
        return "Deezer"
    if "tidal" in u:
        return "Tidal"
    if "soundcloud" in u:
        return "SoundCloud"
    if "youtube" in u or "youtu.be" in u:
        return "YouTube"
    if "spotify" in u:
        return "Spotify"
    return "?"


def sr_to_str(sr) -> str:
    try:
        s = float(str(sr).strip())
    except Exception:
        return ""
    if s <= 0:
        return ""
    khz = s / 1000.0 if s >= 1000 else s
    return f"{khz:.1f}kHz" if abs(khz - round(khz)) > 1e-6 else f"{int(round(khz))}kHz"


def _unwrap_int(x):
    try:
        return int(x)
    except Exception:
        try:
            return int(re.sub(r"[^\d]", "", str(x)))
        except Exception:
            return None


def pretty_label(media) -> str:
    """Album name – Album Artist (bitdepth - samplerate)"""
    meta = getattr(media, "meta", None)
    title = artist = None
    bit_depth = sr = None

    if meta is not None:
        title = getattr(meta, "album", None) or getattr(meta, "title", None) or getattr(meta, "name", None)
        artist = getattr(meta, "albumartist", None) or getattr(meta, "artist", None)
        info = getattr(meta, "info", None)
        if info is not None:
            bit_depth = getattr(info, "bit_depth", None)
            sr = getattr(info, "sampling_rate", None) or getattr(info, "sample_rate", None)
    else:
        title = getattr(media, "title", None) or getattr(media, "name", None)
        artist = getattr(media, "artist", None) or getattr(media, "album_artist", None)
        bit_depth = getattr(media, "bit_depth", None)
        sr = getattr(media, "sample_rate", None)

    if not title and meta is not None:
        title = getattr(meta, "title", None) or getattr(meta, "name", None)
    if not artist and meta is not None:
        artist = getattr(meta, "artist", None)

    bit_depth = _unwrap_int(bit_depth)
    sr_str = sr_to_str(sr)

    core = title or "Unknown"
    if artist:
        core += f" – {artist}"
    tail = []
    if bit_depth:
        tail.append(f"{bit_depth}bit")
    if sr_str:
        tail.append(sr_str)
    if tail:
        core += f" ({' - '.join(tail)})"
    return core


# Dark themes only (human-readable -> xml)
DARK_THEMES = {
    "Dark Amber": "dark_amber.xml",
    "Dark Blue": "dark_blue.xml",
    "Dark Cyan": "dark_cyan.xml",
    "Dark Lightgreen": "dark_lightgreen.xml",
    "Dark Pink": "dark_pink.xml",
    "Dark Purple": "dark_purple.xml",
    "Dark Red": "dark_red.xml",
    "Dark Teal": "dark_teal.xml",
}


# ------------------------- main panel -------------------------

class DownloadPanel(QtWidgets.QWidget):
    """Left side: Add URLs + Queue + internal status bar (dark themes only)."""
    statusChanged = Signal(str)

    def __init__(self, cfg_mgr: ConfigManager, gui_version: str = "streamrip-gui v1 beta", parent=None):
        super().__init__(parent)
        self.cfg_mgr = cfg_mgr
        self.gui_version = gui_version

        self._task: Optional[asyncio.Task] = None
        self._last_vw: Optional[int] = None

        # Static dark style (no dynamic palette = no lag)
        self._style = """
            QWidget { font-size: 11pt; }

            /* Dark titles for sections on the left panel */
            QGroupBox::title { color: #ffffff; font-weight: 700; }

            /* Internal status bar */
            #downloadStatus {
                border-top: 1px solid #3c4043;
                background-color: #26282b;
                color: #ffffff;
            }
            #downloadStatus QLabel { font-size: 12pt; color: #ffffff; }

            /* Inputs: readable text on dark */
            QLabel, QCheckBox, QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTableWidget, QHeaderView::section {
                color: #e6e6e6;
            }
        """

        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setContentsMargins(6, 6, 6, 6)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.setStyleSheet(self._style)

        # Vertical splitter: URLs (top) + Queue (middle)
        self.split = QtWidgets.QSplitter(Qt.Orientation.Vertical)

        # ---- URLs
        gb_urls = QtWidgets.QGroupBox("ADD URLS")
        lv = QtWidgets.QVBoxLayout(gb_urls)

        self.url_edit = QtWidgets.QPlainTextEdit(placeholderText="Paste one URL per line…")
        self.url_edit.setMinimumHeight(120)
        lv.addWidget(self.url_edit, 1)

        btnrow = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("ADD TO QUEUE")
        self.btn_clear = QtWidgets.QPushButton("CLEAR")
        self.btn_start = QtWidgets.QPushButton("START")
        self.btn_stop = QtWidgets.QPushButton("STOP")
        self.btn_stop.setEnabled(False)
        btnrow.addWidget(self.btn_add)
        btnrow.addWidget(self.btn_clear)
        btnrow.addStretch(1)
        btnrow.addWidget(self.btn_start)
        btnrow.addWidget(self.btn_stop)
        lv.addLayout(btnrow)

        # ---- Queue
        gb_q = QtWidgets.QGroupBox("QUEUE")
        rv = QtWidgets.QVBoxLayout(gb_q)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ITEM", "PLATFORM", "STATUS"])
        hh = self.table.horizontalHeader()
        hh.setSectionsMovable(True)
        hh.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)  # user-adjustable
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(self.table.fontMetrics().height(), self.table.fontMetrics().height()))
        rv.addWidget(self.table, 1)

        self.split.addWidget(gb_urls)
        self.split.addWidget(gb_q)
        v.addWidget(self.split, 1)

        # ---- Internal status bar (bottom)
        self.status_frame = QtWidgets.QFrame(objectName="downloadStatus")
        self.status_frame.setMinimumHeight(48)
        sh = QtWidgets.QHBoxLayout(self.status_frame)
        sh.setContentsMargins(12, 6, 12, 6)
        sh.setSpacing(10)

        # left: (blank spacer – dark theme fixed)
        sh.addSpacing(2)

        # center: status
        self.status_center = QtWidgets.QLabel("Idle")
        self.status_center.setAlignment(Qt.AlignCenter)

        # right: version buttons
        right_box = QtWidgets.QWidget()
        right_l = QtWidgets.QHBoxLayout(right_box)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(8)
        self.btn_streamrip = QtWidgets.QPushButton(f"streamrip v{self.cfg_mgr.get_streamrip_version() or 'unknown'}")
        self.btn_gui = QtWidgets.QPushButton(self.gui_version)
        for b in (self.btn_streamrip, self.btn_gui):
            b.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_streamrip.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl("https://github.com/nathom/streamrip")))
        self.btn_gui.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl("https://github.com")))
        right_l.addWidget(self.btn_streamrip)
        right_l.addWidget(self.btn_gui)

        sh.addWidget(QtWidgets.QWidget(), 0)  # left spacer
        sh.addWidget(self.status_center, 1)   # center
        sh.addWidget(right_box, 0)            # right
        v.addWidget(self.status_frame, 0)

        # Wiring
        self.btn_add.clicked.connect(self._add_from_textbox)
        self.btn_clear.clicked.connect(self.url_edit.clear)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)

        # Initialize split + columns once
        QTimer.singleShot(0, self._init_splits_and_columns)

    # ---------- layout helpers ----------
    def _init_splits_and_columns(self):
        total = max(1, self.split.height())
        # 35% (URLs) / 60% (Queue) – status bar fixed height
        self.split.setSizes([int(total * 0.35), int(total * 0.60)])
        self._resize_columns(force=True)

    def resizeEvent(self, e):  # type: ignore[override]
        super().resizeEvent(e)
        self._resize_columns()

    def _resize_columns(self, force: bool = False):
        vw = self.table.viewport().width()
        if vw <= 0:
            return
        if not force and getattr(self, "_last_vw", None) == vw:
            return
        self._last_vw = vw
        hh = self.table.horizontalHeader()
        hh.resizeSection(0, int(vw * 0.70))
        hh.resizeSection(1, int(vw * 0.15))
        hh.resizeSection(2, int(vw * 0.15))

    # ---------- external API ----------
    def add_urls(self, urls: List[str]):
        for u in urls:
            if not u:
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(u))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(infer_platform(u)))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem("Pending"))

    # ---------- internals ----------
    def _set_status(self, text: str):
        self.status_center.setText(text)
        self.statusChanged.emit(text)

    def _add_from_textbox(self):
        lines = [l.strip() for l in self.url_edit.toPlainText().splitlines() if l.strip()]
        if not lines:
            QtWidgets.QMessageBox.warning(self, "Streamrip", "Please paste at least one URL.")
            return
        self.add_urls(lines)
        self.url_edit.clear()

    def _on_resolved(self, media_list: List[object]):
        n = min(len(media_list), self.table.rowCount())
        for i in range(n):
            self.table.item(i, 0).setText(pretty_label(media_list[i]))
            self.table.item(i, 2).setText("Queued")

    def _on_done(self, ok: bool):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        for r in range(self.table.rowCount()):
            self.table.item(r, 2).setText("Done" if ok else "Stopped / check log")
        self._set_status("Finished." if ok else "Stopped / failed")

    def _start(self):
        if self._task and not self._task.done():
            QtWidgets.QMessageBox.information(self, "Streamrip", "A job is already running.")
            return
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.warning(self, "Streamrip", "Queue is empty.")
            return
        loop = asyncio.get_event_loop()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_status("Resolving…")
        urls = [self.table.item(r, 0).text() for r in range(self.table.rowCount())]
        self._task = loop.create_task(self._run(urls))

    def _stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            self._set_status("Stopping…")

    async def _run(self, urls: List[str]):
        from streamrip.rip.main import Main

        cfg = self.cfg_mgr.load()

        # ensure output dir
        out = self.cfg_mgr.get_output_folder()
        if out:
            pathlib.Path(out).mkdir(parents=True, exist_ok=True)

        # creds guard
        need_qobuz = any("qobuz.com" in u for u in urls)
        need_deezer = any("deezer." in u for u in urls)
        q = self.cfg_mgr.get_qobuz()
        d = self.cfg_mgr.get_deezer()
        if need_qobuz and not (q.get("email_or_userid") and q.get("password_or_token")):
            QtWidgets.QMessageBox.information(
                self,
                "Qobuz credentials required",
                "Qobuz URLs detected, but credentials are missing.\nOpen the Qobuz section to set them.",
            )
            self._on_done(False)
            return
        if need_deezer and not d.get("arl"):
            QtWidgets.QMessageBox.information(
                self,
                "Deezer credentials required",
                "Deezer URLs detected, but ARL is missing.\nOpen the Deezer section to set it.",
            )
            self._on_done(False)
            return

        try:
            async with Main(cfg) as main:
                await main.add_all(urls)
                try:
                    await asyncio.wait_for(main.resolve(), timeout=60)
                except asyncio.TimeoutError:
                    logging.getLogger("streamrip").error("Timed out while resolving (check credentials/network).")
                    self._on_done(False)
                    return

                media_list = list(getattr(main, "media", []))
                self._on_resolved(media_list)
                if len(media_list) == 0:
                    self._set_status("Nothing to download.")
                    self._on_done(True)
                    return

                self._set_status(f"Downloading {len(media_list)} item(s)…")
                await main.rip()
                self._on_done(True)

        except asyncio.CancelledError:
            logging.getLogger("streamrip").info("Cancellation requested.")
            self._on_done(False)
        except Exception as e:
            logging.getLogger("streamrip").error(f"Error: {e}")
            self._on_done(False)

    # ---------- theming (dark only) ----------
    def _apply_theme(self):
        """Apply selected dark theme via qt-material (if available)."""
        if _apply_theme is None:
            QtWidgets.QMessageBox.information(self, "Theme", "qt-material is not available in this environment.")
            return
        theme_file = list(DARK_THEMES.values())[0]  # fixed default if you wire a picker later
        app = QtWidgets.QApplication.instance()
        try:
            self.setUpdatesEnabled(False)
            _apply_theme(app, theme=theme_file)
        finally:
            self.setUpdatesEnabled(True)
