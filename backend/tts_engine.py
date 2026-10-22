"""Bước 6: Chuyển văn bản thành giọng nói (TTS) bằng Edge-TTS."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import edge_tts
import os
import subprocess
import yaml
import re
from backend.media_info import get_video_duration

async def _generate_audio_async(text: str, output_path: str, voice: str):
    """Hàm async để gọi Edge-TTS, có cơ chế thử lại."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return True # Thành công
        except Exception as e:
            print(f"[TTS] Lỗi (lần {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2) # Đợi 2 giây rồi thử lại

def _split_text(text: str, max_length: int = 2000) -> list:
    """Chia nhỏ văn bản dài thành các đoạn ngắn để không bị Edge-TTS chặn."""
    # Cắt theo dấu câu (chấm, hỏi, chấm than) để giọng đọc ngắt nghỉ tự nhiên
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # Nếu câu quá dài (không có dấu chấm), cắt theo độ dài
        if len(sentence) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            # Cắt nhỏ câu dài
            for i in range(0, len(sentence), max_length):
                chunks.append(sentence[i:i+max_length].strip())
        else:
            # Nếu thêm câu này vào mà vượt quá max_length -> lưu chunk cũ, bắt đầu chunk mới
            if len(current_chunk) + len(sentence) < max_length:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def text_to_speech(text: str, output_dir: str, voice: str = "vi-VN-HoaiMyNeural") -> tuple:
    """
    Chuyển text thành audio. Trả về (đường_dẫn_file, thời_lượng_giây).
    Chia nhỏ text để tránh lỗi giới hạn của API.
    """
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, "voiceover.mp3")
    
    print(f"[TTS] Đang tạo giọng đọc cho {len(text)} ký tự...")
    
    # 1. Chia nhỏ văn bản
    chunks = _split_text(text, max_length=1500) # Chia mỗi đoạn khoảng 1500 ký tự
    print(f"[TTS] Văn bản được chia thành {len(chunks)} phần để xử lý.")

    if len(chunks) == 1:
        # Nếu văn bản ngắn, tạo trực tiếp
        try:
            asyncio.run(_generate_audio_async(text, final_output_path, voice))
        except Exception as e:
            print(f"[TTS] Lỗi tạo giọng đọc: {e}")
            return None, 0.0
    else:
        # Nếu văn bản dài, tạo nhiều file tạm rồi ghép lại
        temp_files = []
        try:
            for i, chunk in enumerate(chunks):
                temp_path = os.path.join(output_dir, f"temp_{i}.mp3")
                print(f"  -> Đang xử lý phần {i+1}/{len(chunks)}...")
                asyncio.run(_generate_audio_async(chunk, temp_path, voice))
                temp_files.append(temp_path)
            
            # 2. Ghép các file âm thanh bằng FFmpeg
            print("[TTS] Đang ghép các đoạn âm thanh...")
            
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            ffmpeg_exe = os.path.join(cfg["ffmpeg"]["path"], "ffmpeg.exe")
            
            # Tạo file text chứa danh sách file tạm để FFmpeg nối
            list_file = os.path.join(output_dir, "temp_list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for tf in temp_files:
                    f.write(f"file '{tf.replace(chr(92), '/')}'\n")
            
            cmd = [
                ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
                "-i", list_file, "-c", "copy", final_output_path
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Dọn dẹp file tạm
            for tf in temp_files:
                if os.path.exists(tf): os.remove(tf)
            if os.path.exists(list_file): os.remove(list_file)

        except Exception as e:
            print(f"[TTS] Lỗi xử lý văn bản dài: {e}")
            return None, 0.0

    if not os.path.exists(final_output_path):
        return None, 0.0

    # Đo thời lượng file mp3 hoàn chỉnh
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ffprobe_path = os.path.join(cfg["ffmpeg"]["path"], "ffprobe.exe")
    
    duration = get_video_duration(final_output_path, ffprobe_path)
    
    print(f"[TTS] Đã tạo xong. Thời lượng: {duration:.1f} giây")
    return final_output_path, duration

if __name__ == "__main__":
    # Test với văn bản dài
    test_text = "Xin chào các bạn. " * 200 # Tạo một đoạn văn bản rất dài
    audio_path, duration = text_to_speech(test_text, "data/audio_tts")
    print(f"File: {audio_path} | Dài: {duration}s")