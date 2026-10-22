# 🎬 Auto Video Studio

Hệ thống tự động hóa video audio từ văn bản hoặc file âm thanh có sẵn. Dự án kết hợp sức mạnh của AI (Whisper, Edge-TTS, VieNeu-TTS) và FFmpeg để tạo ra những video có giọng đọc hoàn chỉnh chỉ từ một đoạn kịch bản và danh sách link trên Google Sheet.

## ✨ Tính năng chính

- **Lấy văn bản (Whisper):** Tự động trích xuất văn bản (transcript) từ video YouTube/TikTok/Facebook với độ chính xác cao.
- **Tạo Video Tự Động:**
  - Hỗ trợ 2 nguồn âm thanh: Nhập văn bản để AI đọc (TTS) hoặc Tải lên file âm thanh (`.mp3`, `.wav`) có sẵn.
  - **Nhân bản giọng nói (Voice Cloning):** Tích hợp VieNeu-TTS giúp clone giọng đọc từ một file mẫu ngắn (ví dụ: giọng Ngọc Huyền).
  - Tự động tính toán thời lượng âm thanh để tải vừa đủ số lượng video từ Google Sheet (theo chủ đề/Topic).
  - Ghép ngẫu nhiên các video ngắn (TikTok/Shorts) thành một video dài khớp với thời lượng âm thanh.
  - Tự động tắt tiếng video gốc và trộn âm thanh (giọng đọc/file tải lên) vào video thành phẩm.
- **Quản lý dữ liệu:** Đọc và lọc danh sách link video trực tiếp từ Google Sheets.
- **Giao diện Web:** Giao diện hiện đại, dễ sử dụng với 2 tab chức năng riêng biệt.

## 🛠️ Công nghệ sử dụng

- **Backend:** Python, FastAPI
- **Frontend:** HTML, CSS (Tailwind CSS), Vanilla JavaScript
- **AI & Xử lý Media:**
  - `faster-whisper` (Trích xuất văn bản)
  - `edge-tts` (Chuyển văn bản thành giọng nói)
  - `vieneu` (Nhân bản giọng nói)
  - `yt-dlp` (Tải video)
  - `FFmpeg` (Cắt, ghép và xử lý video/audio)
- **Khác:** Google Sheets API (`gspread`)

## 🚀 Hướng dẫn cài đặt

### 1. Yêu cầu hệ thống
- Python 3.9+ (Khuyến nghị 3.10 trở lên).
- [FFmpeg](https://ffmpeg.org/download.html) đã được cài đặt và thêm vào biến môi trường (PATH).

### 2. Cài đặt môi trường
Clone dự án và cài đặt các thư viện cần thiết:

```bash
git clone https://github.com/Doha1610/Auto-video-builder.git
cd Auto-video-builder
python -m venv .venv
# Kích hoạt môi trường ảo (Windows)
.\.venv\Scripts\Activate.ps1
# Cài đặt thư viện
pip install -r requirements.txt

3. Cấu hình
Copy file config1.yaml thành config.yaml.

Mở file config.yaml và điền các thông tin sau:

Đường dẫn tới thư mục bin của FFmpeg.

Thông tin Google Sheet (sheet_id).

Tải file JSON Service Account từ Google Cloud và đặt vào thư mục credentials/google-service.json.

4. Chuẩn bị file giọng mẫu (Nếu dùng tính năng Clone)
Đặt file âm thanh mẫu (ví dụ: Ngọc huyền.mp3) vào thư mục gốc của dự án.

Mở file backend/tts_engine.py, cập nhật đường dẫn file và nội dung chính xác của đoạn audio mẫu ở 2 biến REF_AUDIO_PATH và REF_TEXT.

5. Khởi chạy Server
bash
uvicorn backend.server:app --port 8000
Mở trình duyệt và truy cập: http://localhost:8000

📂 Cấu trúc thư mục
text
Auto-video-builder/
├── backend/            # Mã nguồn xử lý chính (FastAPI, TTS, Whisper, FFmpeg)
├── frontend/           # Giao diện web (HTML, CSS, JS)
├── data/               # Chứa video tải về, audio, video thành phẩm (Bị ignore)
├── credentials/        # Chứa file key Google Cloud (Bị ignore)
├── config1.yaml        # File cấu hình mẫu (Không chứa key thật)
├── requirements.txt    # Danh sách thư viện Python
└── README.md



