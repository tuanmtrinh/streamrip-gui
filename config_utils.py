# config_utils.py
from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable

from streamrip.config import (
    Config,
    DEFAULT_CONFIG_PATH,
    BLANK_CONFIG_PATH,
    OutdatedConfigError,
    set_user_defaults,
)

# ---- Portable / override controls ----
# 1) SR_GUI_CONFIG=/absolute/path/to/config.toml  (highest priority)
# 2) SR_GUI_PORTABLE=1  -> use ./userdata/config.toml next to the EXE
PORTABLE_ENV = "SR_GUI_CONFIG"
PORTABLE_TOGGLE = "1"


def _unwrap(v):
    """Return plain values from tomlkit nodes when present."""
    try:
        return v.unwrap()  # tomlkit nodes
    except Exception:
        return v


def _portable_config_path() -> Path:
    """Path for portable config: ./userdata/config.toml next to the EXE (or module in dev)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    p = base / "userdata" / "config.toml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def resolve_config_path() -> Path:
    """
    Priority:
      1) SR_GUI_CONFIG (explicit absolute path)
      2) SR_GUI_PORTABLE=1 -> ./userdata/config.toml
      3) streamrip.DEFAULT_CONFIG_PATH (per-user app dir)
    """
    p = os.getenv(PORTABLE_ENV)
    if p:
        return Path(p).expanduser()
    if os.getenv(PORTABLE_TOGGLE, "").strip().lower() in {"1", "true", "yes"}:
        return _portable_config_path()
    return Path(DEFAULT_CONFIG_PATH)


def ensure_config_exists(path: Path) -> None:
    """
    Ensure a config file exists at `path`.
    Prefer streamrip's helper `set_user_defaults` (which writes from BLANK_CONFIG_PATH),
    otherwise fall back to copying the template directly.
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        set_user_defaults(str(path))
        return
    except Exception:
        pass
    # Fallback: copy the bundled template
    shutil.copyfile(BLANK_CONFIG_PATH, path)


def load_config() -> Config:
    """
    Load a valid Config:
      - creates from BLANK_CONFIG_PATH if missing
      - migrates older versions in place
    """
    path = resolve_config_path()
    ensure_config_exists(path)
    try:
        return Config(str(path))
    except OutdatedConfigError:
        # migrate old -> new
        Config.update_file(str(path))
        return Config(str(path))


class ConfigManager:
    # Editable keys only (excludes "do not change" fields)
    EDITABLE: Dict[str, Iterable[str]] = {
        "downloads": (
            "folder", "source_subdirectories", "disc_subdirectories", "concurrency",
            "max_connections", "requests_per_minute", "verify_ssl"
        ),
        "conversion": ("enabled", "codec", "sampling_rate", "bit_depth", "lossy_bitrate"),
        "qobuz": ("quality", "download_booklets", "use_auth_token", "email_or_userid", "password_or_token"),
        "deezer": ("quality", "arl", "use_deezloader", "deezloader_warnings"),
        "tidal": ("quality", "download_videos"),
        "soundcloud": ("quality", "client_id", "app_version"),
        "youtube": ("quality", "download_videos", "video_downloads_folder"),
        "database": ("downloads_enabled", "downloads_path", "failed_downloads_enabled", "failed_downloads_path"),
        "qobuz_filters": ("extras", "repeats", "non_albums", "features", "non_studio_albums", "non_remaster"),
        "artwork": ("embed", "embed_size", "embed_max_width", "save_artwork", "saved_max_width"),
        "metadata": ("set_playlist_to_album", "renumber_playlist_tracks", "exclude"),
        "filepaths": ("add_singles_to_folder", "folder_format", "track_format", "restrict_characters", "truncate_to"),
        "lastfm": ("source", "fallback_source"),
        "cli": ("text_output", "progress_bars", "max_search_results"),
        "misc": ("check_for_updates",),  # version is read-only in UI
    }

    def __init__(self, path: str | None = None):
        # Allow caller override; otherwise resolve via env/portable/default chain.
        self.path = Path(path) if path else resolve_config_path()
        ensure_config_exists(self.path)

    def load(self) -> Config:
        return load_config()

    # Convenience
    def get_output_folder(self) -> str:
        cfg = self.load()
        try:
            return str(_unwrap(getattr(cfg.file.downloads, "folder", "")) or "")
        except Exception:
            # legacy fallback
            return str(getattr(cfg.session.downloads, "folder", "") or "")

    def set_output_folder(self, folder: str):
        cfg = self.load()
        cfg.file.downloads.folder = folder
        cfg.file.set_modified()
        cfg.save_file()

    def get_streamrip_version(self) -> str:
        """Read version from config (misc.version) or fall back to package version."""
        try:
            cfg = self.load()
            v = _unwrap(getattr(cfg.file.misc, "version", "")) or ""
            if v:
                return str(v)
        except Exception:
            pass
        try:
            import streamrip
            return getattr(streamrip, "__version__", "unknown")
        except Exception:
            return "unknown"

    def get_section(self, section: str) -> Dict[str, Any]:
        cfg = self.load()
        obj = getattr(cfg.file, section)
        out: Dict[str, Any] = {}
        for key in self.EDITABLE.get(section, []):
            try:
                out[key] = _unwrap(getattr(obj, key))
            except Exception:
                pass
        return out

    def set_section(self, section: str, values: Dict[str, Any]):
        if not values:
            return
        cfg = self.load()
        obj = getattr(cfg.file, section)
        for k, v in values.items():
            if k in self.EDITABLE.get(section, []):
                setattr(obj, k, v)
        cfg.file.set_modified()
        cfg.save_file()

    # helpers for left pane
    def get_qobuz(self):  return self.get_section("qobuz")
    def get_deezer(self): return self.get_section("deezer")
    def set_qobuz(self, **kw):  self.set_section("qobuz",  {k: v for k, v in kw.items() if v is not None})
    def set_deezer(self, **kw): self.set_section("deezer", {k: v for k, v in kw.items() if v is not None})
