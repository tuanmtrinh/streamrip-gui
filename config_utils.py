# config_utils.py
from __future__ import annotations
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable

from streamrip.config import (
    Config,
    DEFAULT_CONFIG_PATH,
    BLANK_CONFIG_PATH,
    OutdatedConfigError,
    set_user_defaults,
)

def _unwrap(v):
    try:
        return v.unwrap()  # tomlkit nodes
    except Exception:
        return v

class ConfigManager:
    # Editable keys only (excludes "do not change" fields)
    EDITABLE: Dict[str, Iterable[str]] = {
        "downloads": ("folder","source_subdirectories","disc_subdirectories","concurrency",
                      "max_connections","requests_per_minute","verify_ssl"),
        "conversion": ("enabled","codec","sampling_rate","bit_depth","lossy_bitrate"),
        "qobuz": ("quality","download_booklets","use_auth_token","email_or_userid","password_or_token"),
        "deezer": ("quality","arl","use_deezloader","deezloader_warnings"),
        "tidal": ("quality","download_videos"),
        "soundcloud": ("quality","client_id","app_version"),
        "youtube": ("quality","download_videos","video_downloads_folder"),
        "database": ("downloads_enabled","downloads_path","failed_downloads_enabled","failed_downloads_path"),
        "qobuz_filters": ("extras","repeats","non_albums","features","non_studio_albums","non_remaster"),
        "artwork": ("embed","embed_size","embed_max_width","save_artwork","saved_max_width"),
        "metadata": ("set_playlist_to_album","renumber_playlist_tracks","exclude"),
        "filepaths": ("add_singles_to_folder","folder_format","track_format","restrict_characters","truncate_to"),
        "lastfm": ("source","fallback_source"),
        "cli": ("text_output","progress_bars","max_search_results"),
        "misc": ("check_for_updates",),  # version is read-only in UI
    }

    def __init__(self, path: str | None = None):
        self.path = Path(path or DEFAULT_CONFIG_PATH)
        self._ensure_exists()

    def _ensure_exists(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            shutil.copyfile(BLANK_CONFIG_PATH, self.path)

    def load(self) -> Config:
        try:
            return Config(str(self.path))
        except OutdatedConfigError:
            # Automatically migrate the user's config to the new schema
            try:
                Config.update_file(str(self.path))
            except Exception:
                # If update fails, fall back to rewriting a fresh template with user defaults
                set_user_defaults(str(self.path))
            return Config(str(self.path))

    # Convenience
    def get_output_folder(self) -> str:
        cfg = self.load()
        try:
            return str(_unwrap(getattr(cfg.file.downloads, "folder", "")) or "")
        except Exception:
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
    def set_qobuz(self, **kw):  self.set_section("qobuz", {k:v for k,v in kw.items() if v is not None})
    def set_deezer(self, **kw): self.set_section("deezer", {k:v for k,v in kw.items() if v is not None})
