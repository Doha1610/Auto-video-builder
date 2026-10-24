"""Xử lý: tải audio + chuyển thành văn bản + kiểm tra chính tả."""
import os
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
from faster_whisper import WhisperModel
import os
os.environ["HF_HOME"] = r"D:\Auto-video-builder\data\hf_cache"
os.environ["VIENEU_HOME"] = r"D:\Auto-video-builder\data\vieneu_cache"
# Đường dẫn FFmpeg - sửa nếu máy bạn khác
FFMPEG_PATH = r"D:\ffmpeg-9.0.1-essentials_build\bin"

# ============ KIỂM TRA CHÍNH TẢ ============
try:
    from autocorrect import Speller
    _spell_vi = Speller(lang='vi')
    _SPELL_AVAILABLE = True
    print("[spell] Đã tải autocorrect tiếng Việt.")
except Exception as e:
    print(f"[warn] Không load được autocorrect: {e}")
    print("[warn] Nút 'Kiểm tra chính tả' sẽ không có tác dụng.")
    _SPELL_AVAILABLE = False
    _spell_vi = None


# Từ điển tự định nghĩa — sửa các từ mà autocorrect không xử lý được
# Thêm cặp (sai → đúng) tuỳ theo video bạn thường xử lý
CUSTOM_CORRECTIONS = {
    # Ví dụ — bạn tự thêm vào
    "chính sác": "chính xác",
    "chính sát": "chính xác",
    "sử lý": "xử lý",
    "sử lí": "xử lý",
    "dành dựt": "giành giật",
    "Nguyên Văn A": "Nguyễn Văn A",
    # Tên riêng, từ chuyên ngành, tiếng lóng...
}


def _apply_custom_corrections(text: str) -> str:
    """Áp dụng từ điển tự định nghĩa."""
    for wrong, right in CUSTOM_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def correct_spelling(text: str, log_fn: Callable[[str], None] = print) -> str:
    """Sửa lỗi chính tả tiếng Việt trong văn bản.

    Quy trình:
    1. Áp dụng từ điển tự định nghĩa (CUSTOM_CORRECTIONS).
    2. Chạy autocorrect để sửa lỗi chung.
    """
    if not text.strip():
        return text

    # Bước 1: Sửa từ điển tự định nghĩa
    text = _apply_custom_corrections(text)

    # Bước 2: autocorrect (nếu có)
    if not _SPELL_AVAILABLE or _spell_vi is None:
        log_fn("[spell] Bỏ qua autocorrect (chưa cài đặt).")
        return text

    try:
        lines = text.split("\n")
        corrected = []
        for line in lines:
            if line.strip():
                corrected.append(_spell_vi(line))
            else:
                corrected.append(line)
        return "\n".join(corrected)
    except Exception as e:
        log_fn(f"[spell] Lỗi khi chạy autocorrect: {e}")
        return text


# ============ TIỆN ÍCH ============
def format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ============ TẢI AUDIO ============
def download_audio(url: str, out_dir: str, log_fn: Callable[[str], None]) -> str:
    """Tải audio từ URL, trả về đường dẫn file mp3."""
    os.makedirs(out_dir, exist_ok=True)

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = got / total * 100
                log_fn(f"[download] {pct:.1f}%")
        elif d["status"] == "finished":
            log_fn("[download] Hoàn tất, đang chuyển sang MP3...")

    opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "outtmpl": os.path.join(out_dir, "%(title).150s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": FFMPEG_PATH,
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    audio_path = filename.rsplit(".", 1)[0] + ".mp3"
    log_fn(f"[download] Đã lưu: {audio_path}")
    return audio_path


# ============ WHISPER ============
def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    language: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
    progress_fn: Callable[[float], None] = lambda p: None,
) -> tuple[str, str]:
    """Chuyển audio thành văn bản. Trả về (text, srt)."""
    log_fn(f"[whisper] Đang tải model {model_size}...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    log_fn("[whisper] Bắt đầu chuyển thành văn bản...")
    segments, info = model.transcribe(
        audio_path, beam_size=5, vad_filter=True, language=language,
    )

    log_fn(f"[whisper] Ngôn ngữ: {info.language} | Thời lượng: {info.duration:.0f}s")

    all_text = []
    srt_lines = []
    idx = 1
    for i, seg in enumerate(segments):
        text = seg.text.strip()
        all_text.append(text)
        srt_lines.append(str(idx))
        srt_lines.append(f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}")
        srt_lines.append(text)
        srt_lines.append("")
        idx += 1

        if info.duration > 0:
            pct = min(seg.end / info.duration, 1.0)
            progress_fn(pct)
            if i % 10 == 0:
                log_fn(f"[whisper] {seg.end:.0f}s / {info.duration:.0f}s ({pct*100:.1f}%)")

    return " ".join(all_text), "\n".join(srt_lines)