"""FastAPI server cho Auto Video Studio."""
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
import random
import shutil
from pathlib import Path
from typing import Optional
import yaml

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import các module xử lý
from backend.transcriber import download_audio, transcribe_audio, correct_spelling
from backend.sheet_reader import read_sheet, group_by_topic
from backend.video_composer import compose_random_video
from backend.tts_engine import text_to_speech
from backend.downloader import download_all, download_one
from backend.media_info import get_video_duration

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

JOBS: dict[str, dict] = {}

class ProcessRequest(BaseModel):
    url: str
    model: str = "small"
    language: Optional[str] = None

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
# API CHO TAB TẢI VIDEO TỪ SHEET
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
# API CHO TAB TẠO VIDEO (TỰ ĐỘNG HOẶC TẢI LÊN)
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
def render_video(
    source_type: str = Form(...), 
    video_format: str = Form("tiktok"),
    audio_source: str = Form("text"),
    topic: str = Form(None),    
    text: str = Form(None),     
    voice: str = Form(None),    
    audio_file: UploadFile = File(None),
    raw_video: UploadFile = File(None)
):
    job_id = _new_job()
    
    saved_audio_path = None
    saved_video_path = None

    if source_type == "auto" and audio_source == "file" and audio_file:
        audio_dir = CONFIG["paths"]["audio_tts_dir"]
        Path(audio_dir).mkdir(parents=True, exist_ok=True)
        saved_audio_path = os.path.join(audio_dir, f"uploaded_{job_id}_{audio_file.filename}")
        with open(saved_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
            
    if source_type == "upload" and raw_video:
        video_dir = CONFIG["paths"]["videos_dir"]
        Path(video_dir).mkdir(parents=True, exist_ok=True)
        saved_video_path = os.path.join(video_dir, f"raw_{job_id}_{raw_video.filename}")
        with open(saved_video_path, "wb") as buffer:
            shutil.copyfileobj(raw_video.file, buffer)

    thread = threading.Thread(
        target=_run_render_job, 
        args=(job_id, text, topic, voice, source_type, audio_source, saved_audio_path, saved_video_path, video_format), 
        daemon=True
    )
    thread.start()
    return {"job_id": job_id}

def _run_render_job(job_id, text, topic, voice, source_type, audio_source, uploaded_audio_path, uploaded_video_path, video_format):
    job = JOBS[job_id]
    job["status"] = "running"
    log = lambda msg: _append_log(job_id, msg)

    try:
        ffmpeg_dir = CONFIG["ffmpeg"]["path"]
        ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
        
        background_path = os.path.abspath("background.png") 
        has_bg = os.path.exists(background_path)
        
        final_video_path = os.path.join(OUTPUT_DIR, f"FINAL_{job_id}.mp4")

        # TRƯỜNG HỢP 1: TẢI VIDEO CÓ SẴN LÊN (CHỈ GHÉP NỀN)
        if source_type == "upload" and uploaded_video_path:
            log(">>> Bước 1: Xử lý video tải lên và ghép nền")
            
            if video_format == "youtube":
                log("Đang render video ngang 16:9...")
                if has_bg:
                    cmd = [
                        ffmpeg_exe, "-y", "-i", background_path, "-i", uploaded_video_path,
                        "-filter_complex", 
                        "[0:v]scale=1920:1080[bg];[1:v]scale=1920:1080:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]",
                        "-map", "[outv]", "-map", "1:a?", 
                        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", final_video_path
                    ]
                else:
                    cmd = [
                        ffmpeg_exe, "-y", "-i", uploaded_video_path,
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", final_video_path
                    ]
            else:
                log("Đang render video dọc 9:16...")
                if has_bg:
                    cmd = [
                        ffmpeg_exe, "-y", "-i", background_path, "-i", uploaded_video_path,
                        "-filter_complex", 
                        "[0:v]scale=1080:1920[bg];[1:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]",
                        "-map", "[outv]", "-map", "1:a?", 
                        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", final_video_path
                    ]
                else:
                    cmd = [
                        ffmpeg_exe, "-y", "-i", uploaded_video_path,
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
                        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", final_video_path
                    ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("LỖI FFMPEG:", result.stderr)
                raise Exception("Lỗi FFmpeg khi ghép nền video.")
                
            job["progress"] = 100
            job["result"] = {"video_url": f"/api/download-final/{job_id}"}
            job["status"] = "done"
            log("=== HOÀN TẤT ===")
            return 

        # TRƯỜNG HỢP 2: TỰ ĐỘNG TẠO TỪ SHEET
        if audio_source == "file" and uploaded_audio_path:
            log(">>> Bước 1: Sử dụng file âm thanh tải lên")
            audio_path = uploaded_audio_path
            ffprobe_path = os.path.join(ffmpeg_dir, "ffprobe.exe")
            duration = get_video_duration(audio_path, ffprobe_path)
            if duration <= 0:
                raise Exception("Không thể đọc thời lượng file âm thanh.")
            log(f"File audio dài {duration:.1f} giây")
        else:
            log(">>> Bước 1: Tạo giọng đọc (TTS)")
            audio_dir = CONFIG["paths"]["audio_tts_dir"]
            audio_path, duration = text_to_speech(text, audio_dir, voice)
            if not audio_path or duration <= 0:
                raise Exception("Lỗi tạo giọng đọc.")
            log(f"Đã tạo audio dài {duration:.1f} giây")
            
        job["progress"] = 20

        log(f">>> Bước 2: Lấy link từ Google Sheet (Topic: {topic})")
        gs = CONFIG["google_sheet"]
        items = read_sheet(gs["sheet_id"], gs["credentials_file"], gs["tab_name"])
        
        if topic:
            items = [i for i in items if i.get("topic", "").strip().lower() == topic.strip().lower()]
        
        if not items:
            raise Exception(f"Không tìm thấy link video nào thuộc topic '{topic}'.")
            
        log(f"Tìm thấy {len(items)} link video cho topic '{topic}'.")
        job["progress"] = 30

        videos_dir = CONFIG["paths"]["videos_dir"]
        images_dir = CONFIG["paths"]["images_dir"]
        
        estimate_videos_needed = int(duration / 10) + 5 
        random.shuffle(items)
        
        log(f"Cần khoảng {estimate_videos_needed} video để đủ {duration:.0f} giây. Bắt đầu tải...")
        
        downloaded_count = 0
        for item in items:
            if downloaded_count >= estimate_videos_needed:
                break
            file_path = download_one(item, videos_dir, images_dir, ffmpeg_dir, skip_if_exists=False)
            if file_path:
                downloaded_count += 1
                job["progress"] = 30 + int((downloaded_count / estimate_videos_needed) * 30)
        
        if downloaded_count == 0:
            raise Exception("Không tải được video nào từ Sheet.")
            
        log(f"Đã tải xong {downloaded_count} video. Bắt đầu ghép...")
        job["progress"] = 60

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
            
        log(f">>> Bước 4: Trộn âm thanh và xuất video {video_format.upper()}")
        job["progress"] = 80
        
        # Ép FFmpeg làm sạch âm thanh (chuyển sang WAV) để tránh lỗi codec
        cleaned_audio_path = os.path.join(OUTPUT_DIR, f"clean_{job_id}.wav")
        cmd_clean = [
            ffmpeg_exe, "-y", "-i", audio_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
            cleaned_audio_path
        ]
        subprocess.run(cmd_clean, capture_output=True, text=True)
        
        if video_format == "youtube":
            log("Đang render video ngang 16:9 cho YouTube...")
            if has_bg:
                cmd_merge = [
                    ffmpeg_exe, "-y",
                    "-err_detect", "ignore_err",
                    "-loop", "1", "-i", background_path,  
                    "-i", temp_output_path,               
                    "-i", cleaned_audio_path,             
                    "-filter_complex", 
                    "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];[1:v]scale=1920:1080:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto[outv]",
                    "-map", "[outv]", "-map", "2:a:0",
                    "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", 
                    final_video_path
                ]
            else:
                cmd_merge = [
                    ffmpeg_exe, "-y", "-err_detect", "ignore_err", "-i", temp_output_path, "-i", cleaned_audio_path,
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                    "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", 
                    final_video_path
                ]
        else:
            log("Đang render video dọc 9:16 cho TikTok...")
            if has_bg:
                cmd_merge = [
                    ffmpeg_exe, "-y",
                    "-err_detect", "ignore_err",
                    "-loop", "1", "-i", background_path,  
                    "-i", temp_output_path,               
                    "-i", cleaned_audio_path,             
                    "-filter_complex", 
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];[1:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto[outv]",
                    "-map", "[outv]", "-map", "2:a:0",
                    "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", 
                    final_video_path
                ]
            else:
                cmd_merge = [
                    ffmpeg_exe, "-y", "-err_detect", "ignore_err", "-i", temp_output_path, "-i", cleaned_audio_path,
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
                    "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", 
                    final_video_path
                ]
        
        result = subprocess.run(cmd_merge, capture_output=True, text=True)
        
        # Dọn dẹp file audio tạm
        if os.path.exists(cleaned_audio_path):
            os.remove(cleaned_audio_path)

        if result.returncode != 0:
            print("LỖI FFMPEG:", result.stderr)
            raise Exception("Lỗi FFmpeg khi trộn âm thanh và xuất video.")
            
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