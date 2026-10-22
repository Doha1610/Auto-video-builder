"""Bước 4 & 5: Tính toán và ghép video ngẫu nhiên bằng FFmpeg."""
import os
import random
import subprocess
import sys
from pathlib import Path

# Thêm đường dẫn gốc để import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.media_info import scan_downloaded_videos

def compose_random_video(videos_dir: str, output_path: str, target_duration: float, ffmpeg_path: str, ffprobe_path: str, topic_filter: str = None):
    """
    Ghép các video ngẫu nhiên trong thư mục để đạt đủ thời lượng target_duration.
    """
    print(f"\n[Composer] Mục tiêu: Ghép video dài {target_duration} giây ({target_duration/60:.1f} phút)")
    
    # 1. Quét danh sách video hiện có
    available_videos = scan_downloaded_videos(videos_dir, ffprobe_path)
    
    if not available_videos:
        print("❌ Không có video nào để ghép!")
        return False

    # 2. Chọn ngẫu nhiên video cho đến khi đủ thời lượng (Tự động loop nếu thiếu)
    selected_videos = []
    current_duration = 0.0
    
    while current_duration < target_duration:
        video = random.choice(available_videos)
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
            break
            
    print(f"-> Đã chọn {len(selected_videos)} đoạn video để ghép.")
    
    # 3. Tạo thư mục đầu ra nếu chưa tồn tại
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    # Tạo file text chứa danh sách video cho FFmpeg
    temp_list_file = os.path.join(out_dir, "temp_concat_list.txt")
    
    with open(temp_list_file, "w", encoding="utf-8") as f:
        for item in selected_videos:
            # Lấy đường dẫn tuyệt đối, thay \ thành /
            abs_path = os.path.abspath(item["path"]).replace("\\", "/")
            
            # Bọc trong dấu nháy đơn để xử lý tên file có khoảng trắng/tiếng Việt
            if item["trim"] is not None:
                f.write(f"file '{abs_path}'\n")
                f.write(f"duration {item['trim']:.3f}\n")
            else:
                f.write(f"file '{abs_path}'\n")
    
    # 4. Gọi FFmpeg để ghép
    print("[Composer] Đang ghép video bằng FFmpeg (quá trình này có thể mất vài phút)...")
    ffmpeg_exe = os.path.join(ffmpeg_path, "ffmpeg.exe")
    
    # ÉP BUỘC RENDER LẠI (Re-encode) ĐỂ ĐỒNG NHẤT ÂM THANH VÀ HÌNH ẢNH
    # Điều này giúp sửa lỗi "Conversion failed" khi video gốc (Facebook/TikTok) bị lỗi codec
    cmd = [
        ffmpeg_exe,
        "-y",                   
        "-f", "concat",         
        "-safe", "0",           
        "-i", temp_list_file,
        "-c:v", "libx264",       # Render lại video sang H.264
        "-preset", "fast",       # Tốc độ render nhanh
        "-c:a", "aac",           # Render lại audio sang AAC
        "-ar", "44100",          # Ép tần số âm thanh chuẩn 44.1kHz
        "-pix_fmt", "yuv420p",   # Đảm bảo tương thích với mọi trình phát
        output_path
    ]
    
    try:
        # Chạy FFmpeg và in lỗi ra nếu có
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Xóa file tạm sau khi ghép xong
        if os.path.exists(temp_list_file):
            os.remove(temp_list_file)
            
        print(f"✅ Ghép thành công! Video lưu tại: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi FFmpeg chi tiết: {e.stderr}")
        if os.path.exists(temp_list_file):
            os.remove(temp_list_file)
        return False