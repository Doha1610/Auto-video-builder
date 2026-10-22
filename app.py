"""Giao diện desktop cho tool chuyển video thành văn bản."""
import os
import queue
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import yt_dlp
from faster_whisper import WhisperModel

# ============ CẤU HÌNH ============
AUDIO_DIR = "audio"
OUTPUT_DIR = "output"
FFMPEG_PATH = r"D:\ffmpeg-9.0.1-essentials_build\bin"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============ HÀM XỬ LÝ ============
def format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def download_audio(url: str, log_fn) -> str:
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = got / total * 100
                log_fn(f"Đang tải... {pct:.1f}%")
        elif d["status"] == "finished":
            log_fn("Tải xong, đang chuyển đổi...")

    opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "outtmpl": f"{AUDIO_DIR}/%(title).150s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": FFMPEG_PATH,
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename.rsplit(".", 1)[0] + ".mp3"


def transcribe_audio(audio_path: str, model_size: str, language, log_fn, progress_fn):
    log_fn(f"Đang tải model {model_size}...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    log_fn("Bắt đầu chuyển thành văn bản...")
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
        language=language,
    )

    log_fn(f"Ngôn ngữ: {info.language} | Thời lượng: {info.duration:.0f}s")

    all_text = []
    srt_lines = []
    srt_index = 1

    for i, seg in enumerate(segments):
        text = seg.text.strip()
        all_text.append(text)

        srt_lines.append(str(srt_index))
        srt_lines.append(f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}")
        srt_lines.append(text)
        srt_lines.append("")
        srt_index += 1

        if info.duration > 0:
            pct = min(seg.end / info.duration, 1.0)
            progress_fn(pct)
            if i % 10 == 0:
                log_fn(f"  ... {seg.end:.0f}s / {info.duration:.0f}s ({pct*100:.1f}%)")

    return " ".join(all_text), "\n".join(srt_lines)


# ============ GIAO DIỆN ============
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Chuyển Video thành Văn bản")
        self.root.geometry("800x650")
        self.is_running = False
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()

        self._build_ui()
        self._poll_queues()

    def _build_ui(self):
        # Frame cấu hình
        config_frame = ttk.LabelFrame(self.root, text="Cấu hình", padding=10)
        config_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(config_frame, text="Model:").grid(row=0, column=0, sticky="w", padx=5)
        self.model_var = tk.StringVar(value="small")
        model_combo = ttk.Combobox(
            config_frame, textvariable=self.model_var,
            values=["tiny", "base", "small", "medium"],
            state="readonly", width=15,
        )
        model_combo.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(config_frame, text="Ngôn ngữ:").grid(row=0, column=2, sticky="w", padx=5)
        self.lang_var = tk.StringVar(value="Tự phát hiện")
        lang_combo = ttk.Combobox(
            config_frame, textvariable=self.lang_var,
            values=["Tự phát hiện", "vi", "en", "zh", "ja", "ko"],
            state="readonly", width=15,
        )
        lang_combo.grid(row=0, column=3, sticky="w", padx=5)

        # URL
        url_frame = ttk.LabelFrame(self.root, text="URL Video", padding=10)
        url_frame.pack(fill="x", padx=10, pady=5)

        self.url_entry = ttk.Entry(url_frame, font=("Segoe UI", 10))
        self.url_entry.pack(fill="x", padx=5, pady=5)
        self.url_entry.insert(0, "Dán URL YouTube hoặc TikTok vào đây...")
        self.url_entry.bind("<FocusIn>", self._clear_placeholder)

        # Nút
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)

        self.start_btn = ttk.Button(
            btn_frame, text="🚀 Bắt đầu", command=self.on_start,
        )
        self.start_btn.pack(side="left", padx=5)

        self.open_btn = ttk.Button(
            btn_frame, text="📁 Mở thư mục output",
            command=lambda: os.startfile(OUTPUT_DIR),
        )
        self.open_btn.pack(side="left", padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=10, pady=5)

        self.status_var = tk.StringVar(value="Sẵn sàng.")
        status_label = ttk.Label(self.root, textvariable=self.status_var)
        status_label.pack(fill="x", padx=10)

        # Log
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, wrap="word",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True)

    def _clear_placeholder(self, event):
        if self.url_entry.get().startswith("Dán URL"):
            self.url_entry.delete(0, "end")

    def log(self, msg):
        self.log_queue.put(msg)

    def set_progress(self, pct):
        self.progress_queue.put(pct)

    def _poll_queues(self):
        # Log
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")

        # Progress
        while not self.progress_queue.empty():
            pct = self.progress_queue.get()
            self.progress["value"] = pct * 100

        self.root.after(100, self._poll_queues)

    def on_start(self):
        if self.is_running:
            messagebox.showinfo("Đang chạy", "Vui lòng đợi tác vụ hiện tại hoàn tất.")
            return

        url = self.url_entry.get().strip()
        if not url or url.startswith("Dán URL"):
            messagebox.showerror("Lỗi", "Bạn chưa nhập URL.")
            return

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.progress["value"] = 0
        self.log_text.delete("1.0", "end")
        self.status_var.set("Đang xử lý...")

        # Chạy ở thread riêng để không đơ giao diện
        thread = threading.Thread(
            target=self._process,
            args=(url, self.model_var.get(), self.lang_var.get()),
            daemon=True,
        )
        thread.start()

    def _process(self, url, model_size, lang_display):
        lang_code = None if lang_display == "Tự phát hiện" else lang_display

        try:
            self.log(f"=== BẮT ĐẦU ===")
            self.log(f"URL: {url}")

            # Bước 1: tải audio
            self.log("")
            self.log(">>> Bước 1: Tải audio")
            audio_path = download_audio(url, self.log)
            self.log(f"Đã tải: {audio_path}")

            # Bước 2: transcribe
            self.log("")
            self.log(">>> Bước 2: Chuyển thành văn bản")
            text, srt = transcribe_audio(
                audio_path, model_size, lang_code,
                self.log, self.set_progress,
            )

            # Bước 3: lưu file
            self.log("")
            self.log(">>> Bước 3: Lưu kết quả")
            base_name = Path(audio_path).stem
            txt_path = Path(OUTPUT_DIR) / f"{base_name}.txt"
            srt_path = Path(OUTPUT_DIR) / f"{base_name}.srt"

            txt_path.write_text(text, encoding="utf-8")
            srt_path.write_text(srt, encoding="utf-8")

            self.log(f"Đã lưu: {txt_path}")
            self.log(f"Đã lưu: {srt_path}")
            self.log("")
            self.log("=== HOÀN TẤT ===")

            self.set_progress(1.0)
            self.status_var.set("✅ Xong! Kiểm tra thư mục output/")

        except Exception as e:
            self.log("")
            self.log("=== LỖI ===")
            self.log(str(e))
            self.log(traceback.format_exc())
            self.status_var.set(f"❌ Lỗi: {e}")

        finally:
            self.is_running = False
            self.start_btn.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()