# config_panel.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal, QTimer

from config_utils import ConfigManager

# ----- Human-readable quality labels (ints still saved) -----
QUALITY_LABELS = {
    0: "128 kbps MP3 or AAC",
    1: "320 kbps MP3 or AAC",
    2: "16-bit, 44.1 kHz (CD)",
    3: "24-bit, up to 96 kHz",
    4: "24-bit, up to 192 kHz",
}

# ----- wheel-proof widgets -----
class NoWheelComboBox(QtWidgets.QComboBox):
    def wheelEvent(self, e):
        if self.view().isVisible():
            return super().wheelEvent(e)
        e.ignore()

class NoWheelSpinBox(QtWidgets.QSpinBox):
    def wheelEvent(self, e): e.ignore()

class NoWheelCheckBox(QtWidgets.QCheckBox):
    def wheelEvent(self, e): e.ignore()

# ----- field schema -----
@dataclass
class FieldSpec:
    key: str
    label: str
    kind: str  # 'bool'|'int'|'int_neg'|'str'|'password'|'combo'|'list'|'path'|'quality'
    opts: Dict[str, Any] | None = None

# ----- full section specs (matches previous full iteration) -----
SECTION_SPECS: Dict[str, Tuple[str, List[FieldSpec]]] = {
    # Downloads / requests
    "downloads": ("Downloads", [
        FieldSpec("folder","Output folder","path"),
        FieldSpec("source_subdirectories","Put albums in source subfolders","bool"),
        FieldSpec("disc_subdirectories","Disc subfolders for multi-disc","bool"),
        FieldSpec("concurrency","Download concurrently","bool"),
        FieldSpec("max_connections","Max concurrent tracks","int_neg", {"min":-1,"max":64}),
        FieldSpec("requests_per_minute","Requests per minute","int_neg", {"min":-1,"max":600}),
        FieldSpec("verify_ssl","Verify SSL certificates","bool"),
    ]),
    # Conversion
    "conversion": ("Conversion", [
        FieldSpec("enabled","Convert after download","bool"),
        FieldSpec("codec","Codec","combo", {"items":["FLAC","ALAC","OPUS","MP3","AAC","OGG"]}),
        FieldSpec("sampling_rate","Downsample above (Hz)","int", {"min":8000,"max":384000,"step":1000}),
        FieldSpec("bit_depth","Target bit depth","combo", {"items":["16","24"]}),
        FieldSpec("lossy_bitrate","Lossy bitrate (kbps)","int", {"min":64,"max":512,"step":32}),
    ]),
    # Services
    "qobuz": ("Qobuz", [
        FieldSpec("quality","Audio quality","quality", {"values":[1,2,3,4]}),
        FieldSpec("download_booklets","Download booklets (PDF)","bool"),
        FieldSpec("use_auth_token","Authenticate with token","bool"),
        FieldSpec("email_or_userid","Email / User ID","str"),
        FieldSpec("password_or_token","Password MD5 / Token","password"),
    ]),
    "deezer": ("Deezer", [
        FieldSpec("quality","Audio quality","quality", {"values":[0,1,2]}),
        FieldSpec("arl","ARL (cookie)","password"),
        FieldSpec("use_deezloader","Use deezloader for free 320","bool"),
        FieldSpec("deezloader_warnings","Warn on deezloader fallback","bool"),
    ]),
    "tidal": ("Tidal", [
        FieldSpec("quality","Audio quality","quality", {"values":[0,1,2,3,4]}),
        FieldSpec("download_videos","Download videos in video albums","bool"),
    ]),
    "soundcloud": ("SoundCloud", [
        FieldSpec("quality","Audio quality","quality", {"values":[0]}),
        FieldSpec("client_id","Client ID","str"),
        FieldSpec("app_version","App version","str"),
    ]),
    "youtube": ("YouTube", [
        FieldSpec("quality","Audio quality","quality", {"values":[0]}),
        FieldSpec("download_videos","Download video + audio","bool"),
        FieldSpec("video_downloads_folder","Video downloads folder","path"),
    ]),
    # Database
    "database": ("Database", [
        FieldSpec("downloads_enabled","Enable downloads DB","bool"),
        FieldSpec("downloads_path","Downloads DB path","path"),
        FieldSpec("failed_downloads_enabled","Enable failed DB","bool"),
        FieldSpec("failed_downloads_path","Failed DB path","path"),
    ]),
    # Qobuz filters
    "qobuz_filters": ("Qobuz Filters", [
        FieldSpec("extras","Remove extras (live/collector)","bool"),
        FieldSpec("repeats","Deduplicate identical titles","bool"),
        FieldSpec("non_albums","Remove EPs/Singles","bool"),
        FieldSpec("features","Remove albums not by artist","bool"),
        FieldSpec("non_studio_albums","Skip non-studio","bool"),
        FieldSpec("non_remaster","Only remasters","bool"),
    ]),
    # Artwork
    "artwork": ("Artwork", [
        FieldSpec("embed","Embed artwork","bool"),
        FieldSpec("embed_size","Embed size","combo", {"items":["thumbnail","small","large","original"]}),
        FieldSpec("embed_max_width","Embed max width (px)","int_neg", {"min":-1,"max":10000}),
        FieldSpec("save_artwork","Save cover as JPG","bool"),
        FieldSpec("saved_max_width","Saved max width (px)","int_neg", {"min":-1,"max":10000}),
    ]),
    # Metadata
    "metadata": ("Metadata", [
        FieldSpec("set_playlist_to_album","Set playlist name as album","bool"),
        FieldSpec("renumber_playlist_tracks","Use playlist order for track #","bool"),
        FieldSpec("exclude","Exclude tags (one per line)","list"),
    ]),
    # Filepaths
    "filepaths": ("Filepaths", [
        FieldSpec("add_singles_to_folder","Singles inside folder_format","bool"),
        FieldSpec("folder_format","Album folder format","str"),
        FieldSpec("track_format","Track filename format","str"),
        FieldSpec("restrict_characters","ASCII-only filenames","bool"),
        FieldSpec("truncate_to","Truncate filename to (chars)","int", {"min":20,"max":255}),
    ]),
    # Last.fm
    "lastfm": ("Last.fm", [
        FieldSpec("source","Primary source","str"),
        FieldSpec("fallback_source","Fallback source","str"),
    ]),
    # CLI / Misc
    "cli": ("CLI", [
        FieldSpec("text_output","Print text output","bool"),
        FieldSpec("progress_bars","Show progress bars","bool"),
        FieldSpec("max_search_results","Max search results","int", {"min":5,"max":1000}),
    ]),
    "misc": ("Misc", [
        FieldSpec("check_for_updates","Check for updates","bool"),
        # (misc.version is read-only and not shown here)
    ]),
}

class ConfigPanel(QtWidgets.QWidget):
    outputFolderChanged = Signal(str)

    def __init__(self, cfg_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.cfg = cfg_mgr
        self._widgets: Dict[tuple[str,str], QtWidgets.QWidget] = {}
        self._groups: Dict[str, QtWidgets.QGroupBox] = {}
        self._build_ui()
        self._load_all()

    # ----- UI -----
    def _build_ui(self):
        self.setContentsMargins(6,6,6,6)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(8)

        # Static dark style (single shot, no palette logic)
        self.setStyleSheet("""
            QWidget { font-size: 11pt; }
            QGroupBox::title { color: #ffffff; font-weight: 700; }
            QLabel, QCheckBox, QLineEdit, QComboBox, QSpinBox, QPlainTextEdit { color: #e6e6e6; }
        """)

        # Header (title + search + feedback + buttons)
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("SETTINGS")
        title.setStyleSheet("font-weight: 700; font-size: 11pt;")
        head.addWidget(title)

        self.search = QtWidgets.QLineEdit(placeholderText="Search settings…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_sections)
        head.addWidget(self.search, 1)

        self.feedback = QtWidgets.QLabel("")
        self.feedback.setMinimumWidth(140)
        head.addWidget(self.feedback)

        self.btn_load_all = QtWidgets.QPushButton("LOAD ALL")
        self.btn_update_all = QtWidgets.QPushButton("UPDATE ALL")
        self.btn_load_all.clicked.connect(self._on_load_all_clicked)
        self.btn_update_all.clicked.connect(self._on_update_all_clicked)
        head.addWidget(self.btn_load_all)
        head.addWidget(self.btn_update_all)

        root.addLayout(head)

        # Scroll container
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(container)
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(8)
        self.scroll.setWidget(container)
        root.addWidget(self.scroll, 1)

        # Build sections
        for sec, (ttl, fields) in SECTION_SPECS.items():
            gb = QtWidgets.QGroupBox(ttl)
            grid = QtWidgets.QGridLayout(gb)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            row = 0
            for fs in fields:
                label = QtWidgets.QLabel(fs.label)
                widget = self._make_widget(fs)
                self._widgets[(sec, fs.key)] = widget
                if fs.kind == "bool":
                    grid.addWidget(label, row, 0)
                    grid.addWidget(widget, row, 1, 1, 2, alignment=Qt.AlignLeft)
                elif fs.kind == "list":
                    grid.addWidget(label, row, 0, alignment=Qt.AlignTop)
                    grid.addWidget(widget, row, 1, 1, 2)
                else:
                    grid.addWidget(label, row, 0)
                    grid.addWidget(widget, row, 1, 1, 2)
                row += 1
            self.vbox.addWidget(gb)
            self._groups[sec] = gb

        self.vbox.addStretch(1)

    # ----- widget factory -----
    def _make_widget(self, fs: FieldSpec) -> QtWidgets.QWidget:
        k = fs.kind
        if k == "bool":
            return NoWheelCheckBox()
        if k == "int":
            sp = NoWheelSpinBox()
            sp.setRange(fs.opts.get("min", 0), fs.opts.get("max", 10**9))
            sp.setSingleStep(fs.opts.get("step", 1))
            return sp
        if k == "int_neg":
            sp = NoWheelSpinBox()
            sp.setRange(fs.opts.get("min", -1), fs.opts.get("max", 10**9))
            sp.setSingleStep(fs.opts.get("step", 1))
            return sp
        if k == "combo":
            cb = NoWheelComboBox()
            for item in fs.opts.get("items", []):
                cb.addItem(item, item)
            cb.setMinimumWidth(160)
            return cb
        if k == "password":
            le = QtWidgets.QLineEdit(); le.setEchoMode(QtWidgets.QLineEdit.Password); return le
        if k == "path":
            roww = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(roww); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
            le = QtWidgets.QLineEdit(); btn = QtWidgets.QPushButton("BROWSE…")
            def pick():
                d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose folder", le.text() or "")
                if d: le.setText(d)
            btn.clicked.connect(pick)
            h.addWidget(le,1); h.addWidget(btn)
            roww._lineedit = le  # type: ignore
            return roww
        if k == "list":
            te = QtWidgets.QPlainTextEdit(); te.setPlaceholderText("One per line"); te.setMinimumHeight(70); return te
        if k == "quality":
            cb = NoWheelComboBox()
            for v in fs.opts.get("values", [0,1,2,3,4]):
                cb.addItem(QUALITY_LABELS.get(v, str(v)), v)
            cb.setMinimumWidth(240)
            return cb
        return QtWidgets.QLineEdit()

    # ----- load/save -----
    def _load_all(self):
        for sec in SECTION_SPECS.keys():
            self._load_section(sec)

    def _update_all(self):
        changed = False
        for sec in SECTION_SPECS.keys():
            changed |= self._save_section(sec)
        if changed:
            folder = self.cfg.get_output_folder()
            if folder:
                self.outputFolderChanged.emit(folder)

    def _load_section(self, section: str):
        data = self.cfg.get_section(section)
        _, fields = SECTION_SPECS[section]
        for fs in fields:
            self._set_widget_value(self._widgets[(section, fs.key)], fs, data.get(fs.key))

    def _save_section(self, section: str) -> bool:
        out: Dict[str, Any] = {}
        fresh = self.cfg.get_section(section)
        _, fields = SECTION_SPECS[section]
        for fs in fields:
            w = self._widgets[(section, fs.key)]
            v = self._get_widget_value(w, fs)
            # For text-like types: if empty, keep existing value (don’t overwrite with "")
            if fs.kind in ("str","password","path","list"):
                if not (v if isinstance(v, list) else str(v or "").strip()):
                    # restore field view to current config value so UI reflects actual saved value
                    self._set_widget_value(w, fs, fresh.get(fs.key))
                    continue
            out[fs.key] = v
        if out:
            self.cfg.set_section(section, out)
            return True
        return False

    # ----- widget value helpers -----
    def _set_widget_value(self, w: QtWidgets.QWidget, fs: FieldSpec, val: Any):
        if fs.kind == "bool":
            w: NoWheelCheckBox; w.setChecked(bool(val))
        elif fs.kind in ("int","int_neg"):
            w: NoWheelSpinBox; w.setValue(int(val or 0))
        elif fs.kind == "combo":
            w: NoWheelComboBox
            idx = w.findData(val if val is not None else "")
            if idx < 0: idx = w.findText(str(val or ""), Qt.MatchFixedString)
            if idx >= 0: w.setCurrentIndex(idx)
        elif fs.kind == "quality":
            w: NoWheelComboBox
            try: target = int(val)
            except Exception: target = None
            if target is not None:
                for i in range(w.count()):
                    if w.itemData(i) == target:
                        w.setCurrentIndex(i); break
        elif fs.kind == "path":
            le: QtWidgets.QLineEdit = w._lineedit  # type: ignore
            le.setText(str(val or ""))
        elif fs.kind == "list":
            te: QtWidgets.QPlainTextEdit = w  # type: ignore
            if isinstance(val, (list, tuple)): te.setPlainText("\n".join(map(str,val)))
            else: te.setPlainText(str(val or ""))
        else:
            le: QtWidgets.QLineEdit = w  # type: ignore
            le.setText(str(val or ""))

    def _get_widget_value(self, w: QtWidgets.QWidget, fs: FieldSpec):
        if fs.kind == "bool":
            w: NoWheelCheckBox; return w.isChecked()
        if fs.kind in ("int","int_neg"):
            w: NoWheelSpinBox; return int(w.value())
        if fs.kind == "combo":
            w: NoWheelComboBox; return w.currentData() or w.currentText()
        if fs.kind == "quality":
            w: NoWheelComboBox
            try: return int(w.currentData())
            except Exception: return 0
        if fs.kind == "path":
            le: QtWidgets.QLineEdit = w._lineedit  # type: ignore
            return le.text().strip()
        if fs.kind == "list":
            te: QtWidgets.QPlainTextEdit = w  # type: ignore
            raw = te.toPlainText().strip()
            return [s.strip() for s in raw.replace(",", "\n").splitlines() if s.strip()]
        le: QtWidgets.QLineEdit = w  # type: ignore
        return le.text().strip()

    # ----- search + feedback -----
    def _filter_sections(self, text: str):
        q = (text or "").lower().strip()
        for sec, gb in self._groups.items():
            title, _ = SECTION_SPECS[sec]
            vis = True
            if q:
                vis = (q in title.lower()) or self._group_contains(gb, q)
            gb.setVisible(vis)

    def _group_contains(self, gb: QtWidgets.QGroupBox, q: str) -> bool:
        for lab in gb.findChildren(QtWidgets.QLabel):
            if q in (lab.text() or "").lower(): return True
        for le in gb.findChildren(QtWidgets.QLineEdit):
            if q in (le.text() or "").lower(): return True
        for te in gb.findChildren(QtWidgets.QPlainTextEdit):
            if q in (te.toPlainText() or "").lower(): return True
        return False

    def _flash_feedback(self, text: str):
        self.feedback.setText(text)
        QTimer.singleShot(2000, lambda: self.feedback.setText(""))

    def _on_load_all_clicked(self):
        self._load_all()
        self._flash_feedback("Config loaded")

    def _on_update_all_clicked(self):
        self._update_all()
        self._flash_feedback("Config updated")
