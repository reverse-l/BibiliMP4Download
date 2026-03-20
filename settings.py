from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {
    "save_dir": str((Path.home() / "Downloads").resolve()),
    "quality": "1080P",
    "audio_only": False,
    "audio_format": "mp3",
    "merge_output_format": "mp4",
    "filename_template": "%(title)s [%(id)s].%(ext)s",
    "download_subtitles": False,
    "download_danmaku": False,
    "playlist": False,
    "proxy": "",
    "retries": 10,
    "concurrent_fragments": 3,
    "cookie_file": "",
    "cookie_browser": "",
    "browser_profile": "",
}


class SettingsStore:
    def __init__(self, app_name: str = "bili_downloader_gui") -> None:
        app_data = Path.home() / ".config" / app_name
        if not app_data.exists():
            app_data = Path.home() / f".{app_name}"
        app_data.mkdir(parents=True, exist_ok=True)
        self.path = app_data / "settings.json"

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return dict(DEFAULT_SETTINGS)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_SETTINGS)

    def save(self, data: Dict[str, Any]) -> None:
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        self.path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
