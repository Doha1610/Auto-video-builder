import sys
import traceback
import yt_dlp
from faster_whisper import WhisperModel


def download_audio(url, out_dir="audio"):
    import os
    os.makedirs(out_dir, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "outtmpl": f"{out_dir}/%(title).150s.%(ext)s",
        "quiet": False,
        "ffmpeg_location": r"D:\ffmpeg-9.0.1-essentials_build\bin",
    }
    print(f"[DEBUG] Bắt đầu tải: {url}")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    print(f"[DEBUG] File gốc: {filename}")
    return filename.rsplit(".", 1)[0] + ".mp3"


def format_timestamp(seconds):
    """Đổi giây -> HH:MM:SS,mmm cho định dạng SRT."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(audio_path, model_size="small"):
    print(f"[DEBUG] Bắt đầu transcribe: {audio_path}")
    model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
    )
    segments, info = model.transcribe(
        audio_path, beam_size=5, vad_filter=True
    )
    print(f"Ngôn ngữ: {info.language}, thời lượng: {info.duration:.0f}s")
    print("Đang xử lý... (in tiến độ mỗi 50 đoạn)")

    all_text = []
    srt_lines = []

    for i, seg in enumerate(segments):
        text = seg.text.strip()
        all_text.append(text)

        # Ghi SRT
        srt_lines.append(str(len(srt_lines) // 4 + 1))
        srt_lines.append(f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}")
        srt_lines.append(text)
        srt_lines.append("")

        # In tiến độ mỗi 50 đoạn
        if i % 50 == 0 and i > 0:
            pct = (seg.end / info.duration * 100) if info.duration else 0
            print(f"  ... đã xử lý {seg.end:.0f}s / {info.duration:.0f}s ({pct:.1f}%)")

    return " ".join(all_text), "\n".join(srt_lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("LỖI: Bạn chưa truyền URL.")
        print('Cách dùng: python transcribe.py "URL_VIDEO"')
        sys.exit(1)

    url = sys.argv[1]
    print(f"[DEBUG] URL nhận được: {url}")

    try:
        print("Đang tải audio...")
        audio = download_audio(url)
        print(f"Đã tải: {audio}")

        print("Đang chuyển thành văn bản...")
        text, srt = transcribe(audio)

        base = audio.replace(".mp3", "").replace("audio/", "").replace("audio\\", "")

        # Ghi .txt
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Đã lưu .txt: {base}.txt")

        # Ghi .srt
        with open(base + ".srt", "w", encoding="utf-8") as f:
            f.write(srt)
        print(f"Đã lưu .srt: {base}.srt")

        print("Xong!")

    except Exception as e:
        print("\n=== LỖI XẢY RA ===")
        traceback.print_exc()
        sys.exit(1)