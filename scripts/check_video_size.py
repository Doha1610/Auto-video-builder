"""Script kiểm tra kích thước video trong Google Sheet và ghi kết quả."""
import sys
import os
import yaml
import subprocess
import json
from pathlib import Path

# Thêm đường dẫn gốc để import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def get_video_info(url: str, ytdlp_path: str = "yt-dlp") -> str:
    """Dùng yt-dlp để lấy độ phân giải và thời lượng mà không cần tải video."""
    try:
        # Lệnh yt-dlp lấy thông tin JSON
        cmd = [
            ytdlp_path, 
            "--dump-json", 
            "--no-playlist",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        width = info.get("width", 0)
        height = info.get("height", 0)
        duration = info.get("duration", 0)
        
        # Nếu là video ngắn (Shorts/Reels), có thể width/height bị null, dùng format
        if not width or not height:
            for fmt in info.get("formats", []):
                if fmt.get("vcodec") != "none" and fmt.get("width"):
                    width = fmt["width"]
                    height = fmt["height"]
                    break
                    
        if width and height:
            return f"{width}x{height} ({duration}s)"
        return f"Lỗi: Không lấy được kích thước ({duration}s)"
    except subprocess.CalledProcessError as e:
        return "Lỗi: Không thể tải thông tin"
    except Exception as e:
        return f"Lỗi: {str(e)[:20]}"

def main():
    # Đọc cấu hình
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
        
    gs_cfg = cfg["google_sheet"]
    creds = Credentials.from_service_account_file(gs_cfg["credentials_file"], scopes=SCOPES)
    client = gspread.authorize(creds)
    
    # Mở Sheet
    sheet = client.open_by_key(gs_cfg["sheet_id"]).worksheet(gs_cfg["tab_name"])
    
    # Lấy toàn bộ dữ liệu
    records = sheet.get_all_records()
    
    if not records:
        print("Sheet trống!")
        return

    # Tìm cột "Kiểm tra kích thước" (cột E)
    headers = sheet.row_values(1)
    col_name = "Kiểm tra kích thước"
    
    if col_name not in headers:
        print(f"Không tìm thấy cột '{col_name}' trên Sheet. Vui lòng thêm cột này ở dòng 1.")
        return
        
    col_index = headers.index(col_name) + 1
    print(f"Bắt đầu kiểm tra {len(records)} link video...\n")
    
    # Lặp qua từng dòng
    for i, row in enumerate(records):
        row_num = i + 2 # Dòng 1 là header, nên dữ liệu bắt đầu từ dòng 2
        url = str(row.get("link", "")).strip()
        
        if not url:
            continue
            
        print(f"[{i+1}/{len(records)}] Đang kiểm tra: {url}")
        
        # Nếu cột đã có dữ liệu thì bỏ qua (tránh kiểm tra lại)
        if row.get(col_name) and str(row.get(col_name)).strip() != "":
            print("  -> Đã kiểm tra, bỏ qua.")
            continue
            
        info = get_video_info(url)
        print(f"  -> Kết quả: {info}")
        
        # Ghi vào Google Sheet
        sheet.update_cell(row_num, col_index, info)
        
    print("\n✅ Đã kiểm tra và cập nhật xong Google Sheet!")

if __name__ == "__main__":
    main()
#python scripts/check_video_size.py