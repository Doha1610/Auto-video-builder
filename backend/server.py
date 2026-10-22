"""FastAPI server cho Auto Video Studio."""
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
import random
from pathlib import Path
from typing import Optional
import yaml

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import các module xử lý
from backend.transcriber import download_audio, transcribe_audio, correct_spelling
from backend.sheet_reader import read_sheet, group_by_topic
from backend.video_composer import compose_random_video
from backend.tts_engine import text_to_speech
from backend.downloader import download_all, download_one

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = str(BASE_DIR / "audio")
OUTPUT_DIR = str(BASE_DIR / "output")
FRONTEND_DIR = str(BASE_DIR / "frontend")
CONFIG_FILE = str(BASE_DIR / "config.yaml")

# Đọc cấu hình
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Tự động tạo các thư mục cần thiết nếu chưa có
Path(CONFIG["paths"]["video_composed_dir"]).mkdir(parents=True, exist_ok=True)
Path(CONFIG["paths"]["audio_tts_dir"]).mkdir(parents=True, exist_ok=True)
Path(CONFIG["paths"]["videos_dir"]).mkdir(parents=True, exist_ok=True)
Path(CONFIG["paths"]["images_dir"]).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Auto Video Studio")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lưu trạng thái các job đang chạy
JOBS: dict[str, dict] = {}

class ProcessRequest(BaseModel):
    url: str
    model: str = "small"
    language: Optional[str] = None

class RenderRequest(BaseModel):
    text: str
    topic: str
    voice: str = "vi-VN-HoaiMyNeural"

def _new_job() -> str:
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {
        "status": "pending",
        "logs": [],
        "progress": 0.0,
        "result": None,
        "error": None,
        "started_at": time.time(),
    }
    return job_id

def _append_log(job_id: str, msg: str):
    job = JOBS.get(job_id)
    if job:
        job["logs"].append({"t": time.time(), "msg": msg})

@app.get("/api/health")
def health_check():
    return {"ok": True, "version": "real", "pid": os.getpid()}

# ==========================================
# API CHO TAB TẢI VIDEO TỪ SHEET (HÀNG LOẠT)
# ==========================================
@app.post("/api/download-sheet")
def download_from_sheet():
    job_id = _new_job()
    thread = threading.Thread(target=_run_download_job, args=(job_id,), daemon=True)
    thread.start()
    return {"job_id": job_id}

def _run_download_job(job_id):
    job = JOBS[job_id]
    job["status"] = "running"
    log = lambda msg: _append_log(job_id, msg)

    try:
        log("Đang kết nối tới Google Sheet...")
        gs = CONFIG["google_sheet"]
        items = read_sheet(gs["sheet_id"], gs["credentials_file"], gs["tab_name"])
        
        if not items:
            raise Exception("Không tìm thấy link nào trong Sheet.")
            
        log(f"Tìm thấy {len(items)} link. Bắt đầu tải...")
        
        results = download_all(
            items,
            videos_dir=CONFIG["paths"]["videos_dir"],
            images_dir=CONFIG["paths"]["images_dir"],
            ffmpeg_path=CONFIG["ffmpeg"]["path"],
            skip_if_exists=True
        )
        
        success = sum(1 for r in results if r["ok"])
        log(f"=== HOÀN TẤT: Tải thành công {success}/{len(items)} file ===")
        
        job["progress"] = 100
        job["result"] = {"success": success, "total": len(items)}
        job["status"] = "done"
        
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        log(f"LỖI: {e}")

# ==========================================
# API CHO TAB TẠO VIDEO (TỰ ĐỘNG TẢI ĐỦ + GHÉP + TRỘN AUDIO)
# ==========================================
@app.get("/api/topics")
def get_topics():
    try:
        gs = CONFIG["google_sheet"]
        items = read_sheet(gs["sheet_id"], gs["credentials_file"], gs["tab_name"])
        groups = group_by_topic(items)
        return {"topics": list(groups.keys())}
    except Exception as e:
        return {"topics": []}

@app.post("/api/render-video")
def render_video(req: RenderRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Văn bản trống")

    job_id = _new_job()
    thread = threading.Thread(target=_run_render_job, args=(job_id, req.text, req.topic, req.voice), daemon=True)
    thread.start()
    return {"job_id": job_id}

def _run_render_job(job_id, text, topic, voice):
    job = JOBS[job_id]
    job["status"] = "running"
    log = lambda msg: _append_log(job_id, msg)

    try:
        # BƯỚC 1: TẠO GIỌNG ĐỌC
        log(">>> Bước 1: Tạo giọng đọc (TTS)")
        audio_dir = CONFIG["paths"]["audio_tts_dir"]
        audio_path, duration = text_to_speech(text, audio_dir, voice)
        
        if not audio_path or duration <= 0:
            raise Exception("Lỗi tạo giọng đọc.")
        
        log(f"Đã tạo audio dài {duration:.1f} giây")
        job["progress"] = 20

        # BƯỚC 2: TẢI VỪA ĐỦ SỐ LƯỢNG VIDEO CẦN THIẾT
        log(f">>> Bước 2: Lấy link từ Google Sheet (Topic: {topic})")
        gs = CONFIG["google_sheet"]
        items = read_sheet(gs["sheet_id"], gs["credentials_file"], gs["tab_name"])
        
        # Lọc link theo topic
        if topic:
            items = [i for i in items if i.get("topic", "").strip().lower() == topic.strip().lower()]
        
        if not items:
            raise Exception(f"Không tìm thấy link video nào thuộc topic '{topic}' trong Sheet.")
            
        log(f"Tìm thấy {len(items)} link video cho topic '{topic}'.")
        job["progress"] = 30

        videos_dir = CONFIG["paths"]["videos_dir"]
        images_dir = CONFIG["paths"]["images_dir"]
        ffmpeg_dir = CONFIG["ffmpeg"]["path"]
        
        # Ước lượng số video cần tải (giả sử mỗi video dài 15s, + 2 video dự phòng)
        estimate_videos_needed = int(duration / 15) + 2 
        
        # Xáo trộn để tải ngẫu nhiên
        random.shuffle(items)
        links_to_download = items[:estimate_videos_needed]
        
        log(f"Cần khoảng {estimate_videos_needed} video. Bắt đầu tải...")
        
        for i, item in enumerate(links_to_download):
            download_one(
                item, 
                videos_dir=videos_dir, 
                images_dir=images_dir, 
                ffmpeg_path=ffmpeg_dir, 
                skip_if_exists=True
            )
            job["progress"] = 30 + int(((i+1) / len(links_to_download)) * 30)
        
        log("Tải video hoàn tất. Bắt đầu ghép...")
        job["progress"] = 60

        # BƯỚC 3: GHÉP VIDEO HÌNH ẢNH
        log(">>> Bước 3: Ghép video ngẫu nhiên")
        temp_output_filename = f"temp_{job_id}.mp4"
        temp_output_path = os.path.join(CONFIG["paths"]["video_composed_dir"], temp_output_filename)
        
        success = compose_random_video(
            videos_dir=videos_dir,
            output_path=temp_output_path,
            target_duration=duration,
            ffmpeg_path=ffmpeg_dir,
            ffprobe_path=os.path.join(ffmpeg_dir, "ffprobe.exe"),
            topic_filter=None
        )

        if not success:
            raise Exception("Lỗi ghép video.")
            
        # BƯỚC 4: TRỘN ÂM THANH VÀO VIDEO
        log(">>> Bước 4: Tắt tiếng video gốc và chèn giọng đọc")
        job["progress"] = 80
        
        final_video_path = os.path.join(OUTPUT_DIR, f"FINAL_{job_id}.mp4")
        ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
        
        cmd_merge = [
            ffmpeg_exe, "-y",
            "-i", temp_output_path,  # Input 0: Video gốc (có tiếng ồn)
            "-i", audio_path,        # Input 1: Giọng đọc
            "-map", "0:v:0",         # Chỉ lấy hình ảnh của video 0
            "-map", "1:a:0",         # Chỉ lấy âm thanh của video 1 (giọng đọc)
            "-c:v", "copy",          # Không render lại hình ảnh
            "-c:a", "aac",           # Render âm thanh sang AAC
            "-shortest",             # Dừng khi giọng đọc kết thúc
            final_video_path
        ]
        
        result = subprocess.run(cmd_merge, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("LỖI FFMPEG:", result.stderr)
            raise Exception("Lỗi FFmpeg khi trộn âm thanh.")
            
        # Dọn dẹp file video tạm không tiếng
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)

        job["progress"] = 100
        job["result"] = {"video_url": f"/api/download-final/{job_id}"}
        job["status"] = "done"
        log("=== HOÀN TẤT ===")

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        log(f"LỖI: {e}")
        log(traceback.format_exc())

@app.get("/api/download-final/{job_id}")
def download_final_video(job_id: str):
    path = Path(OUTPUT_DIR) / f"FINAL_{job_id}.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại")
    
    # Thêm các header để báo cho trình duyệt biết đây là file tĩnh, không cần ngắt kết nối
    return FileResponse(
        path, 
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"}
    )


# ==========================================
# API CHO TAB WHISPER (LẤY VĂN BẢN)
# ==========================================
def _run_whisper_job(job_id: str, url: str, model: str, language: Optional[str]):
    job = JOBS[job_id]
    job["status"] = "running"
    log = lambda msg: _append_log(job_id, msg)

    try:
        log(f"Bắt đầu tải audio từ: {url}")
        audio_path = download_audio(url, AUDIO_DIR, log)

        log(">>> Bắt đầu chuyển thành văn bản...")
        def set_progress(p): job["progress"] = round(p * 100, 1)
        
        text, srt = transcribe_audio(audio_path, model_size=model, language=language, log_fn=log, progress_fn=set_progress)

        base_name = Path(audio_path).stem
        txt_path = Path(OUTPUT_DIR) / f"{base_name}.txt"
        srt_path = Path(OUTPUT_DIR) / f"{base_name}.srt"

        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        txt_path.write_text(text, encoding="utf-8")
        srt_path.write_text(srt, encoding="utf-8")

        job["progress"] = 100.0
        job["result"] = {
            "txt_name": txt_path.name, "srt_name": srt_path.name, "text": text,
            "txt_path": str(txt_path), "srt_path": str(srt_path),
        }
        job["status"] = "done"
        log("=== HOÀN TẤT ===")

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        log(f"LỖI: {e}")

@app.post("/api/process")
def start_process(req: ProcessRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL trống")
    job_id = _new_job()
    threading.Thread(target=_run_whisper_job, args=(job_id, req.url.strip(), req.model, req.language), daemon=True).start()
    return {"job_id": job_id}

@app.get("/api/progress/{job_id}")
def get_progress(job_id: str, since: int = 0):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return {
        "status": job["status"], "progress": job["progress"],
        "logs": job["logs"][since:], "log_count": len(job["logs"]),
        "result": job["result"], "error": job["error"],
    }

@app.get("/api/download/{job_id}/{kind}")
def download_result(job_id: str, kind: str):
    job = JOBS.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Không có kết quả")
    if kind == "txt":
        path, fname = job["result"]["txt_path"], job["result"]["txt_name"]
    elif kind == "srt":
        path, fname = job["result"]["srt_path"], job["result"]["srt_name"]
    else:
        raise HTTPException(status_code=400, detail="kind không hợp lệ")
    return FileResponse(path, filename=fname, media_type="text/plain")

@app.post("/api/correct/{job_id}")
def correct_job_text(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=400, detail="Chưa có kết quả")
    new_text = correct_spelling(job["result"]["text"], log_fn=lambda m: _append_log(job_id, m))
    job["result"]["text"] = new_text
    Path(job["result"]["txt_path"]).write_text(new_text, encoding="utf-8")
    return {"ok": True, "text": new_text}

@app.get("/api/open-output")
def open_output_folder():
    path = os.path.abspath(OUTPUT_DIR)
    os.makedirs(path, exist_ok=True)
    try:
        if sys.platform == "win32": os.startfile(path)
        else: subprocess.Popen(["xdg-open", path])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if Path(FRONTEND_DIR).exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")