from __future__ import annotations

import threading
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from yt_dlp import YoutubeDL


@dataclass
class DownloadOptions:
    save_dir: str
    quality: str
    audio_only: bool
    audio_format: str
    merge_output_format: str
    filename_template: str
    download_subtitles: bool
    download_danmaku: bool
    playlist: bool
    proxy: str
    retries: int
    concurrent_fragments: int
    cookie_file: str
    cookie_browser: str
    browser_profile: str


class CallbackLogger:
    def __init__(self, callback: Callable[[str], None]) -> None:
        self.callback = callback

    def debug(self, msg: str) -> None:
        if msg.strip():
            self.callback(msg)

    def warning(self, msg: str) -> None:
        self.callback(f"[WARN] {msg}")

    def error(self, msg: str) -> None:
        self.callback(f"[ERROR] {msg}")


QUALITY_TO_FORMAT = {
    "Best": "bv*+ba/b",
    "1080P": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720P": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480P": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360P": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

QUALITY_TO_SINGLE_FILE_FORMAT = {
    "Best": "best[vcodec!=none][acodec!=none]/best",
    "1080P": "best[height<=1080][vcodec!=none][acodec!=none]/best[height<=1080]",
    "720P": "best[height<=720][vcodec!=none][acodec!=none]/best[height<=720]",
    "480P": "best[height<=480][vcodec!=none][acodec!=none]/best[height<=480]",
    "360P": "best[height<=360][vcodec!=none][acodec!=none]/best[height<=360]",
}


class BiliDownloader:
    def __init__(
        self,
        log_callback: Callable[[str], None],
        progress_callback: Callable[[float, str], None],
        stop_event: threading.Event,
    ) -> None:
        self.log = log_callback
        self.progress = progress_callback
        self.stop_event = stop_event

    def _resolve_ffmpeg(self) -> str | None:
        ffmpeg_on_path = shutil.which("ffmpeg")
        if ffmpeg_on_path:
            return ffmpeg_on_path

        home = Path.home()
        candidates = [
            Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
            Path(r"C:\Program Files\FFmpeg\bin\ffmpeg.exe"),
            home / r"AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",
        ]
        candidates.extend((home / r"AppData\Local\Microsoft\WinGet\Packages").glob("**/ffmpeg.exe"))

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return None

    def _progress_hook(self, item: dict) -> None:
        if self.stop_event.is_set():
            raise KeyboardInterrupt("用户已停止任务")

        status = item.get("status")
        if status == "downloading":
            total = item.get("total_bytes") or item.get("total_bytes_estimate") or 0
            current = item.get("downloaded_bytes") or 0
            speed = item.get("speed")
            speed_text = ""
            if speed:
                speed_text = f" | {speed / 1024 / 1024:.2f} MB/s"
            percent = (current / total * 100) if total else 0.0
            self.progress(percent, f"下载中 {percent:.1f}%{speed_text}")
        elif status == "finished":
            self.progress(100.0, "下载完成，正在处理文件...")

    def _build_ydl_opts(self, options: DownloadOptions) -> dict:
        save_dir = Path(options.save_dir).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_path = self._resolve_ffmpeg()
        ffmpeg_available = ffmpeg_path is not None

        if options.audio_only:
            if not ffmpeg_available:
                raise ValueError("仅音频模式依赖 FFmpeg。请安装 FFmpeg 后重试，或改为视频模式下载。")
            ydl_format = "bestaudio/best"
        else:
            if ffmpeg_available:
                ydl_format = QUALITY_TO_FORMAT.get(options.quality, QUALITY_TO_FORMAT["1080P"])
            else:
                ydl_format = QUALITY_TO_SINGLE_FILE_FORMAT.get(options.quality, QUALITY_TO_SINGLE_FILE_FORMAT["1080P"])
                self.log("[WARN] 未检测到 FFmpeg，已自动降级为单文件格式下载（不执行音视频合并）")

        ydl_opts = {
            "format": ydl_format,
            "outtmpl": str(save_dir / options.filename_template),
            "noplaylist": not options.playlist,
            "writesubtitles": options.download_subtitles,
            "writeautomaticsub": options.download_subtitles,
            "retries": max(1, int(options.retries)),
            "concurrent_fragment_downloads": max(1, int(options.concurrent_fragments)),
            "logger": CallbackLogger(self.log),
            "progress_hooks": [self._progress_hook],
            "ignoreerrors": False,
            "continuedl": True,
        }

        if ffmpeg_available:
            ydl_opts["ffmpeg_location"] = ffmpeg_path
            ydl_opts["merge_output_format"] = options.merge_output_format

        if options.proxy.strip():
            ydl_opts["proxy"] = options.proxy.strip()

        if options.cookie_file.strip():
            ydl_opts["cookiefile"] = options.cookie_file.strip()

        if options.cookie_browser.strip():
            browser = options.cookie_browser.strip().lower()
            profile = options.browser_profile.strip()
            if profile:
                ydl_opts["cookiesfrombrowser"] = (browser, None, profile, None)
            else:
                ydl_opts["cookiesfrombrowser"] = (browser,)

        if options.audio_only:
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": options.audio_format,
                    "preferredquality": "320",
                }
            ]

        if options.download_danmaku:
            ydl_opts["writesubtitles"] = True

        return ydl_opts

    def download(self, urls: Iterable[str], options: DownloadOptions) -> None:
        url_list = [u.strip() for u in urls if u.strip()]
        if not url_list:
            raise ValueError("请输入至少一个 B 站视频链接")

        ydl_opts = self._build_ydl_opts(options)
        self.progress(0.0, "任务开始")
        self.log(f"准备下载 {len(url_list)} 个链接")

        try:
            with YoutubeDL(ydl_opts) as ydl:
                for index, url in enumerate(url_list, start=1):
                    if self.stop_event.is_set():
                        raise KeyboardInterrupt("用户已停止任务")
                    self.log(f"[{index}/{len(url_list)}] {url}")
                    ydl.download([url])

            self.progress(100.0, "全部任务已完成")
            self.log("全部下载任务完成")
        except KeyboardInterrupt as exc:
            self.progress(0.0, "任务已停止")
            self.log(str(exc))
        except Exception as exc:
            self.progress(0.0, "任务失败")
            self.log(f"下载失败: {exc}")
            raise
