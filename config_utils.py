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

PORTABLE_ENV = "SR_GUI_CONFIG"
PORTABLE_TOGGLE = "SR_GUI_PORTABLE"


def _unwrap(v):
    """Return plain values from tomlkit nodes when present."""
    try:
        return v.unwrap()
    except Exception:
        return v


def _portable_config_path() -> Path:
    """
    Path for portable config: ./userdata/config.toml next to the EXE
    (or next to this file in dev).
    """
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
    explicit = os.getenv(PORTABLE_ENV)
    if explicit:
        return Path(explicit).expanduser()

    toggle = os.getenv(PORTABLE_TOGGLE, "").strip().lower()
    if toggle in {"1", "true", "yes"}:
        return _portable_config_path()

    return Path(DEFAULT_CONFIG_PATH)


def ensure_config_exists(path: Path) -> None:
    """
    Ensure a config file exists at `path`.
    Prefer streamrip's helper `set_user_defaults` (writes from BLANK_CONFIG_PATH),
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

        try:
            Config.update_file(str(path))
        except Exception:
            set_user_defaults(str(path))
        return Config(str(path))


class ConfigManager:
    """
    Thin wrapper providing generic read/write access to config sections.
    Use:
        cfg = ConfigManager()
        downloads = cfg.get_section("downloads")
        cfg.set_section("downloads", {"folder": "D:/Music", "verify_ssl": True})
    """

    EDITABLE: Dict[str, Iterable[str]] = {
        "downloads": (
            "folder",
            "source_subdirectories",
            "disc_subdirectories",
            "concurrency",
            "max_connections",
            "requests_per_minute",
            "verify_ssl",
        ),
        "conversion": (
            "enabled",
            "codec",
            "sampling_rate",
            "bit_depth",
            "lossy_bitrate",
        ),
        "qobuz": (
            "quality",
            "download_booklets",
            "use_auth_token",
            "email_or_userid",
            "password_or_token",
        ),
        "deezer": ("quality", "arl", "use_deezloader", "deezloader_warnings"),
        "tidal": ("quality", "download_videos"),
        "soundcloud": ("quality", "client_id", "app_version"),
        "youtube": ("quality", "download_videos", "video_downloads_folder"),
        "database": (
            "downloads_enabled",
            "downloads_path",
            "failed_downloads_enabled",
            "failed_downloads_path",
        ),
        "qobuz_filters": (
            "extras",
            "repeats",
            "non_albums",
            "features",
            "non_studio_albums",
            "non_remaster",
        ),
        "artwork": (
            "embed",
            "embed_size",
            "embed_max_width",
            "save_artwork",
            "saved_max_width",
        ),
        "metadata": ("set_playlist_to_album", "renumber_playlist_tracks", "exclude"),
        "filepaths": (
            "add_singles_to_folder",
            "folder_format",
            "track_format",
            "restrict_characters",
            "truncate_to",
        ),
        "lastfm": ("source", "fallback_source"),
        "cli": ("text_output", "progress_bars", "max_search_results"),
        "misc": ("check_for_updates",),
    }

    def __init__(self, path: str | None = None):

        self.path = Path(path) if path else resolve_config_path()
        ensure_config_exists(self.path)

    def load(self) -> Config:
        return load_config()

    def get_output_folder(self) -> str:
        cfg = self.load()
        try:
            return str(_unwrap(getattr(cfg.file.downloads, "folder", "")) or "")
        except Exception:

            return str(
                getattr(
                    getattr(cfg, "session", object()), "downloads", object()
                ).__dict__.get("folder", "")
                or ""
            )

    def set_output_folder(self, folder: str) -> None:
        cfg = self.load()
        cfg.file.downloads.folder = folder
        cfg.file.set_modified()
        cfg.save_file()

    def get_streamrip_version(self) -> str:
        """Read version from config (misc.version) or fall back to package version."""
        try:
            v = _unwrap(getattr(self.load().file.misc, "version", "")) or ""
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
        result: Dict[str, Any] = {}
        for key in self.EDITABLE.get(section, []):
            try:
                result[key] = _unwrap(getattr(obj, key))
            except Exception:
                pass
        return result

    def set_section(self, section: str, values: Dict[str, Any]) -> None:
        if not values:
            return
        cfg = self.load()
        obj = getattr(cfg.file, section)
        editable = set(self.EDITABLE.get(section, []))
        for k, v in values.items():
            if k in editable:
                setattr(obj, k, v)
        cfg.file.set_modified()
        cfg.save_file()
