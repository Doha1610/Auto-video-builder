"""Bước 4 & 5: Ghép video siêu an toàn (One-liner FFmpeg)."""
import os
import random
import subprocess
import sys
import json
import shutil
from pathlib import Path

# Thêm đường dẫn gốc để import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.media_info import scan_downloaded_videos

def get_video_resolution(file_path, ffprobe_path):
    cmd = [
        ffprobe_path, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if data.get("streams"):
            return f"{data['streams'][0]['width']}x{data['streams'][0]['height']}"
    except:
        pass
    return "unknown"

def compose_random_video(videos_dir: str, output_path: str, target_duration: float, ffmpeg_path: str, ffprobe_path: str, topic_filter: str = None):
    print(f"\n[Composer] Mục tiêu: Ghép video dài {target_duration} giây ({target_duration/60:.1f} phút)")
    
    available_videos = scan_downloaded_videos(videos_dir, ffprobe_path)
    if not available_videos:
        print("❌ Không có video nào để ghép!")
        return False

    random.shuffle(available_videos)

    # Lọc ra danh sách các video sẽ dùng cho đến khi đủ thời lượng
    selected_paths = []
    current_duration = 0.0
    last_path = None

    while current_duration < target_duration:
        if len(available_videos) > 1:
            video = random.choice([v for v in available_videos if v["path"] != last_path])
        else:
            video = available_videos[0]
            
        last_path = video["path"]
        remain = target_duration - current_duration
        
        # Đưa vào danh sách
        selected_paths.append(video["path"])
        current_duration += min(video["duration"], remain)
        
        # Nếu video bị cắt bớt thì dừng vòng lặp
        if video["duration"] > remain:
            break

    print(f"-> Đã chọn {len(selected_paths)} video. Bắt đầu render 1 lần duy nhất...")

    # Xây dựng câu lệnh FFmpeg khổng lồ (One-liner)
    ffmpeg_exe = os.path.join(ffmpeg_path, "ffmpeg.exe")
    
    # 1. Tạo danh sách các tham số -i (input)
    input_args = []
    for path in selected_paths:
        input_args.extend(["-i", path])

    # 2. Tạo bộ lọc filter_complex
    # - scale & pad: Ép mọi video về 1080x1920, thêm viền đen nếu lệch tỷ lệ
    # - fps=30: Ép tốc độ khung hình
    # - setsar=1: Đồng bộ tỷ lệ điểm ảnh
    filter_complex = ""
    for i in range(len(selected_paths)):
        filter_complex += f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30,setsar=1[v{i}];"
    
    # Nối tất cả các video lại với nhau
    concat_inputs = "".join([f"[v{i}]" for i in range(len(selected_paths))])
    filter_complex += f"{concat_inputs}concat=n={len(selected_paths)}:v=1:a=0[outv]"

    # 3. Tạo lệnh cuối cùng
    cmd = [ffmpeg_exe, "-y"] + input_args + [
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        output_path
    ]

    try:
        print("[Composer] Đang render (quá trình này có thể mất vài phút)...")
        # Chạy lệnh và in log ra nếu lỗi
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Lỗi FFmpeg chi tiết:\n", result.stderr[-500:])
            return False
            
        print(f"✅ Ghép thành công! Video lưu tại: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")
        return False