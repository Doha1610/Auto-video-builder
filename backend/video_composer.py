"""Bước 4 & 5: Tính toán và ghép video ngẫu nhiên (Nhóm theo kích thước)."""
import os
import random
import subprocess
import sys
import json
from pathlib import Path
from collections import defaultdict

# Thêm đường dẫn gốc để import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.media_info import scan_downloaded_videos

def get_video_resolution(file_path, ffprobe_path):
    """Lấy kích thước WxH của video."""
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
    """
    Ghép các video ngẫu nhiên, ưu tiên ghép các video cùng kích thước với nhau trước.
    """
    print(f"\n[Composer] Mục tiêu: Ghép video dài {target_duration} giây ({target_duration/60:.1f} phút)")
    
    available_videos = scan_downloaded_videos(videos_dir, ffprobe_path)
    if not available_videos:
        print("❌ Không có video nào để ghép!")
        return False

    # 1. NHÓM VIDEO THEO KÍCH THƯỚC
    grouped_videos = defaultdict(list)
    for video in available_videos:
        res = get_video_resolution(video["path"], ffprobe_path)
        grouped_videos[res].append(video)
    
    print(f"-> Đã tìm thấy các nhóm kích thước: {list(grouped_videos.keys())}")

    selected_videos = []
    current_duration = 0.0
    
    # 2. CHỌN VIDEO ƯU TIÊN CÙNG NHÓM
    # Lấy ngẫu nhiên một nhóm để bắt đầu (ưu tiên nhóm có nhiều video)
    groups_list = list(grouped_videos.keys())
    random.shuffle(groups_list)
    
    for group_res in groups_list:
        group_list = grouped_videos[group_res]
        
        # Lặp qua các video trong cùng nhóm này cho đến khi đầy
        while group_list and current_duration < target_duration:
            video = random.choice(group_list)
            remain = target_duration - current_duration
            
            if video["duration"] <= remain:
                selected_videos.append({
                    "path": video["path"],
                    "duration": video["duration"],
                    "trim": None
                })
                current_duration += video["duration"]
            else:
                selected_videos.append({
                    "path": video["path"],
                    "duration": video["duration"],
                    "trim": remain
                })
                current_duration += remain
                break # Đã đủ thời lượng
        
        if current_duration >= target_duration:
            break

    # Nếu vẫn chưa đủ thời lượng (do hết video), lặp lại toàn bộ danh sách
    while current_duration < target_duration:
        video = random.choice(available_videos)
        remain = target_duration - current_duration
        if video["duration"] <= remain:
            selected_videos.append({"path": video["path"], "duration": video["duration"], "trim": None})
            current_duration += video["duration"]
        else:
            selected_videos.append({"path": video["path"], "duration": video["duration"], "trim": remain})
            current_duration += remain
            break

    print(f"-> Đã chọn {len(selected_videos)} đoạn video. Tổng thời lượng: {current_duration:.1f}s")
    
    # 3. TẠO DANH SÁCH FILE TẠM
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    temp_list_file = os.path.join(out_dir, "temp_concat_list.txt")
    
    with open(temp_list_file, "w", encoding="utf-8") as f:
        for item in selected_videos:
            abs_path = os.path.abspath(item["path"]).replace("\\", "/")
            if item["trim"] is not None:
                f.write(f"file '{abs_path}'\n")
                f.write(f"duration {item['trim']:.3f}\n")
            else:
                f.write(f"file '{abs_path}'\n")
    
    # 4. GỌI FFMPEG ĐỂ GHÉP
    print("[Composer] Đang ghép video (quá trình này có thể mất vài phút)...")
    ffmpeg_exe = os.path.join(ffmpeg_path, "ffmpeg.exe")
    
    # Ép chuẩn hóa video (nếu có lệch kích thước nhỏ) để tránh lỗi codec
    cmd = [
        ffmpeg_exe,
        "-y",                   
        "-f", "concat",         
        "-safe", "0",           
        "-i", temp_list_file,
        "-c:v", "libx264",       
        "-preset", "fast",       
        "-c:a", "aac",           
        "-ar", "44100",          
        "-pix_fmt", "yuv420p",   
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if os.path.exists(temp_list_file):
            os.remove(temp_list_file)
        print(f"✅ Ghép thành công! Video lưu tại: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi FFmpeg chi tiết: {e.stderr}")
        if os.path.exists(temp_list_file):
            os.remove(temp_list_file)
        return False