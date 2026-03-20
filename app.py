from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from downloader import BiliDownloader, DownloadOptions
from settings import SettingsStore


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DownloaderApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("B站视频下载器 Pro")
        self.geometry("1080x760")
        self.minsize(980, 700)

        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self._load_settings_to_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="B站视频下载器 Pro",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title.grid(row=0, column=0, padx=18, pady=(14, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="支持单视频 / 合集，支持音频提取与多项高级设置（仅用于合法授权内容下载）",
            text_color=("gray25", "gray70"),
            font=ctk.CTkFont(size=13),
        )
        subtitle.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_right_panel(body)

        footer = ctk.CTkFrame(self)
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(footer, text="就绪", anchor="w")
        self.status_label.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")

        self.progress = ctk.CTkProgressBar(footer)
        self.progress.set(0)
        self.progress.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        left = ctk.CTkFrame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(5, weight=1)

        url_label = ctk.CTkLabel(left, text="视频链接（每行一个）", font=ctk.CTkFont(size=15, weight="bold"))
        url_label.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        self.url_text = ctk.CTkTextbox(left, height=170)
        self.url_text.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")

        path_frame = ctk.CTkFrame(left, fg_color="transparent")
        path_frame.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        path_frame.grid_columnconfigure(0, weight=1)

        self.save_dir_entry = ctk.CTkEntry(path_frame, placeholder_text="保存目录")
        self.save_dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        browse_btn = ctk.CTkButton(path_frame, text="选择目录", width=100, command=self._pick_dir)
        browse_btn.grid(row=0, column=1)

        control_frame = ctk.CTkFrame(left, fg_color="transparent")
        control_frame.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="ew")
        control_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_btn = ctk.CTkButton(control_frame, text="开始下载", command=self._start_download)
        self.start_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.stop_btn = ctk.CTkButton(control_frame, text="停止", fg_color="#B22222", hover_color="#8B1A1A", command=self._stop_download)
        self.stop_btn.grid(row=0, column=1, padx=6, sticky="ew")

        save_btn = ctk.CTkButton(control_frame, text="保存设置", command=self._save_settings)
        save_btn.grid(row=0, column=2, padx=(6, 0), sticky="ew")

        log_label = ctk.CTkLabel(left, text="下载日志", font=ctk.CTkFont(size=15, weight="bold"))
        log_label.grid(row=4, column=0, padx=14, pady=(2, 6), sticky="w")

        self.log_text = ctk.CTkTextbox(left)
        self.log_text.grid(row=5, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.log_text.configure(state="disabled")

    def _build_right_panel(self, parent: ctk.CTkFrame) -> None:
        right = ctk.CTkScrollableFrame(parent)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="下载设置", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(10, 10), sticky="w"
        )

        self.quality_var = ctk.StringVar(value="1080P")
        self.quality_box = self._setting_row(
            right,
            1,
            "画质",
            lambda frame: ctk.CTkComboBox(frame, values=["Best", "1080P", "720P", "480P", "360P"], variable=self.quality_var),
        )

        self.audio_only_var = ctk.BooleanVar(value=False)
        self._setting_row(
            right,
            2,
            "模式",
            lambda frame: ctk.CTkSwitch(frame, text="仅下载音频", variable=self.audio_only_var),
        )

        self.audio_format_var = ctk.StringVar(value="mp3")
        self._setting_row(
            right,
            3,
            "音频格式",
            lambda frame: ctk.CTkComboBox(frame, values=["mp3", "m4a", "wav", "flac"], variable=self.audio_format_var),
        )

        self.merge_format_var = ctk.StringVar(value="mp4")
        self._setting_row(
            right,
            4,
            "视频封装",
            lambda frame: ctk.CTkComboBox(frame, values=["mp4", "mkv", "webm"], variable=self.merge_format_var),
        )

        self.filename_entry = self._setting_row(right, 5, "命名模板", lambda frame: ctk.CTkEntry(frame))

        self.subtitles_var = ctk.BooleanVar(value=False)
        self._setting_row(
            right,
            6,
            "字幕",
            lambda frame: ctk.CTkSwitch(frame, text="下载字幕（自动字幕）", variable=self.subtitles_var),
        )

        self.danmaku_var = ctk.BooleanVar(value=False)
        self._setting_row(
            right,
            7,
            "弹幕",
            lambda frame: ctk.CTkSwitch(frame, text="下载弹幕相关数据", variable=self.danmaku_var),
        )

        self.playlist_var = ctk.BooleanVar(value=False)
        self._setting_row(
            right,
            8,
            "合集",
            lambda frame: ctk.CTkSwitch(frame, text="下载合集/分P", variable=self.playlist_var),
        )

        self.proxy_entry = self._setting_row(right, 9, "代理", lambda frame: ctk.CTkEntry(frame, placeholder_text="如: http://127.0.0.1:7890"))

        self.retry_entry = self._setting_row(right, 10, "重试次数", lambda frame: ctk.CTkEntry(frame))

        self.fragments_entry = self._setting_row(right, 11, "分片并发", lambda frame: ctk.CTkEntry(frame))

        def _build_cookie_row(frame: ctk.CTkFrame) -> ctk.CTkFrame:
            cookie_file_frame = ctk.CTkFrame(frame, fg_color="transparent")
            cookie_file_frame.grid_columnconfigure(0, weight=1)
            self.cookie_file_entry = ctk.CTkEntry(cookie_file_frame, placeholder_text="cookies.txt 路径")
            self.cookie_file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            ctk.CTkButton(cookie_file_frame, text="选择", width=70, command=self._pick_cookie_file).grid(row=0, column=1)
            return cookie_file_frame

        self._setting_row(right, 12, "Cookie文件", _build_cookie_row)

        self.cookie_browser_var = ctk.StringVar(value="")
        self._setting_row(
            right,
            13,
            "浏览器Cookie",
            lambda frame: ctk.CTkComboBox(
                frame,
                values=["", "chrome", "edge", "firefox", "brave", "chromium"],
                variable=self.cookie_browser_var,
            ),
        )

        self.browser_profile_entry = self._setting_row(
            right,
            14,
            "浏览器Profile",
            lambda frame: ctk.CTkEntry(frame, placeholder_text="浏览器 Profile，如 Default"),
        )

        tips = ctk.CTkLabel(
            right,
            text="提示：音频模式会自动使用 FFmpeg 提取；请确保系统可用 ffmpeg。",
            justify="left",
            wraplength=300,
            text_color=("gray30", "gray70"),
        )
        tips.grid(row=15, column=0, padx=10, pady=(14, 16), sticky="w")

    def _setting_row(self, parent: ctk.CTkFrame, row: int, label_text: str, widget_factory):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=10, pady=6)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=label_text).grid(row=0, column=0, sticky="w", pady=(0, 4))
        widget = widget_factory(frame)
        widget.grid(row=1, column=0, sticky="ew")
        return widget

    def _pick_dir(self) -> None:
        selected = filedialog.askdirectory(title="选择下载目录")
        if selected:
            self.save_dir_entry.delete(0, "end")
            self.save_dir_entry.insert(0, selected)

    def _pick_cookie_file(self) -> None:
        selected = filedialog.askopenfilename(title="选择 cookies.txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if selected:
            self.cookie_file_entry.delete(0, "end")
            self.cookie_file_entry.insert(0, selected)

    def _load_settings_to_ui(self) -> None:
        self.save_dir_entry.delete(0, "end")
        self.save_dir_entry.insert(0, self.settings.get("save_dir", str(Path.home())))

        self.quality_var.set(self.settings.get("quality", "1080P"))
        self.audio_only_var.set(bool(self.settings.get("audio_only", False)))
        self.audio_format_var.set(self.settings.get("audio_format", "mp3"))
        self.merge_format_var.set(self.settings.get("merge_output_format", "mp4"))

        self.filename_entry.delete(0, "end")
        self.filename_entry.insert(0, self.settings.get("filename_template", "%(title)s [%(id)s].%(ext)s"))

        self.subtitles_var.set(bool(self.settings.get("download_subtitles", False)))
        self.danmaku_var.set(bool(self.settings.get("download_danmaku", False)))
        self.playlist_var.set(bool(self.settings.get("playlist", False)))

        self.proxy_entry.delete(0, "end")
        self.proxy_entry.insert(0, self.settings.get("proxy", ""))

        self.retry_entry.delete(0, "end")
        self.retry_entry.insert(0, str(self.settings.get("retries", 10)))

        self.fragments_entry.delete(0, "end")
        self.fragments_entry.insert(0, str(self.settings.get("concurrent_fragments", 3)))

        self.cookie_file_entry.delete(0, "end")
        self.cookie_file_entry.insert(0, self.settings.get("cookie_file", ""))

        self.cookie_browser_var.set(self.settings.get("cookie_browser", ""))

        self.browser_profile_entry.delete(0, "end")
        self.browser_profile_entry.insert(0, self.settings.get("browser_profile", ""))

    def _collect_options(self) -> DownloadOptions:
        try:
            retries = int(self.retry_entry.get().strip() or "10")
            fragments = int(self.fragments_entry.get().strip() or "3")
        except ValueError as exc:
            raise ValueError("重试次数和分片并发必须是整数") from exc

        save_dir = self.save_dir_entry.get().strip()
        if not save_dir:
            raise ValueError("请先选择保存目录")

        return DownloadOptions(
            save_dir=save_dir,
            quality=self.quality_var.get(),
            audio_only=self.audio_only_var.get(),
            audio_format=self.audio_format_var.get(),
            merge_output_format=self.merge_format_var.get(),
            filename_template=self.filename_entry.get().strip() or "%(title)s [%(id)s].%(ext)s",
            download_subtitles=self.subtitles_var.get(),
            download_danmaku=self.danmaku_var.get(),
            playlist=self.playlist_var.get(),
            proxy=self.proxy_entry.get().strip(),
            retries=retries,
            concurrent_fragments=fragments,
            cookie_file=self.cookie_file_entry.get().strip(),
            cookie_browser=self.cookie_browser_var.get().strip(),
            browser_profile=self.browser_profile_entry.get().strip(),
        )

    def _save_settings(self) -> None:
        try:
            options = self._collect_options()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return

        self.settings_store.save(options.__dict__)
        self._append_log("设置已保存")
        self.status_label.configure(text="设置已保存")

    def _set_running(self, running: bool) -> None:
        state_start = "disabled" if running else "normal"
        state_stop = "normal" if running else "disabled"
        self.start_btn.configure(state=state_start)
        self.stop_btn.configure(state=state_stop)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_progress(self, percent: float, status_text: str) -> None:
        value = max(0.0, min(100.0, percent)) / 100.0

        def _ui_update() -> None:
            self.progress.set(value)
            self.status_label.configure(text=status_text)

        self.after(0, _ui_update)

    def _start_download(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("提示", "当前已有下载任务正在进行")
            return

        urls = self.url_text.get("1.0", "end").splitlines()

        try:
            options = self._collect_options()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self.settings_store.save(options.__dict__)
        self.stop_event.clear()
        self._set_running(True)
        self._append_log("开始下载任务...")

        def _runner() -> None:
            downloader = BiliDownloader(
                log_callback=lambda msg: self.after(0, self._append_log, msg),
                progress_callback=self._update_progress,
                stop_event=self.stop_event,
            )
            try:
                downloader.download(urls, options)
            except Exception as exc:
                self.after(0, messagebox.showerror, "下载失败", str(exc))
            finally:
                self.after(0, self._set_running, False)

        self.worker = threading.Thread(target=_runner, daemon=True)
        self.worker.start()

    def _stop_download(self) -> None:
        self.stop_event.set()
        self._append_log("已请求停止，请等待当前分片结束...")


def main() -> None:
    app = DownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
