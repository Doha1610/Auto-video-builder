"""Lấy thông tin media (thời lượng, kích thước) bằng ffprobe."""
import json
import subprocess
import os
import yaml

def get_video_duration(file_path: str, ffprobe_path: str) -> float:
    """Trả về thời lượng video (giây). Trả về 0.0 nếu lỗi."""
    if not os.path.exists(file_path):
        return 0.0

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[ffprobe] Lỗi đọc file {file_path}: {e}")
        return 0.0


def scan_downloaded_videos(videos_dir: str, ffprobe_path: str) -> list:
    """Quét thư mục, trả về danh sách các video kèm thời lượng."""
    if not os.path.exists(videos_dir):
        print(f"❌ Thư mục không tồn tại: {videos_dir}")
        return []

    files = [f for f in os.listdir(videos_dir) if f.endswith(".mp4")]
    if not files:
        print(f"❌ Không có file .mp4 nào trong thư mục: {videos_dir}")
        return []

    videos = []
    for filename in files:
        path = os.path.join(videos_dir, filename)
        duration = get_video_duration(path, ffprobe_path)
        if duration > 0:
            videos.append({
                "path": path,
                "filename": filename,
                "duration": duration
            })
    
    # Sắp xếp theo thời lượng tăng dần
    videos.sort(key=lambda x: x["duration"])
    return videos


if __name__ == "__main__":
    # Đọc config
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    
    # Lấy đường dẫn FFmpeg/ffprobe từ config
    ffmpeg_dir = cfg["ffmpeg"]["path"]
    ffprobe_path = os.path.join(ffmpeg_dir, "ffprobe.exe")
    
    videos_dir = cfg["paths"]["videos_dir"]
    
    print(f"Đang quét thư mục: {videos_dir} ...")
    videos = scan_downloaded_videos(videos_dir, ffprobe_path)
    
    if videos:
        print(f"\n✅ Tìm thấy {len(videos)} video:")
        for v in videos[:10]: # Chỉ in 10 video đầu để đỡ dài
            print(f" - {v['filename']}: {v['duration']:.1f} giây")
        if len(videos) > 10:
            print(f" ... và {len(videos) - 10} video khác.")
    else:
        print("\nKhông có video nào để xử lý.")