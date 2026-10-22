"""Bước 2: Tải video/ảnh từ danh sách link về máy."""
import hashlib
import os
from pathlib import Path
from typing import Optional

import requests
import yt_dlp


def _short_hash(text: str) -> str:
    """Tạo tên file ngắn từ URL, tránh trùng lặp."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _is_tiktok(url: str) -> bool:
    return "tiktok.com" in url


def download_image(
    url: str,
    out_dir: str,
    timeout: int = 30,
    skip_if_exists: bool = True,
) -> Optional[str]:
    """Tải ảnh về. Trả về đường dẫn file hoặc None nếu lỗi."""
    os.makedirs(out_dir, exist_ok=True)
    ext = Path(url.split("?")[0]).suffix or ".jpg"
    out_path = os.path.join(out_dir, f"img_{_short_hash(url)}{ext}")

    if skip_if_exists and os.path.exists(out_path):
        print(f"[image] Đã có, bỏ qua: {out_path}")
        return out_path

    try:
        r = requests.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"[image] Đã tải: {out_path}")
        return out_path
    except Exception as e:
        print(f"[image] Lỗi tải {url}: {e}")
        return None


def download_video(
    url: str,
    out_dir: str,
    ffmpeg_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> Optional[str]:
    """Tải video từ YouTube/TikTok về máy. Trả về đường dẫn file .mp4."""
    os.makedirs(out_dir, exist_ok=True)
    file_id = _short_hash(url)

    # Nếu đã có file cùng hash → bỏ qua
    if skip_if_exists:
        for f in os.listdir(out_dir):
            if f.startswith(f"vid_{file_id}") and f.endswith(".mp4"):
                existing = os.path.join(out_dir, f)
                print(f"[video] Đã có, bỏ qua: {existing}")
                return existing

    outtmpl = os.path.join(out_dir, f"vid_{file_id}.%(ext)s")

    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "noplaylist": True,
    }

    if ffmpeg_path:
        opts["ffmpeg_location"] = ffmpeg_path

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # Đảm bảo trả về file .mp4
        base, _ = os.path.splitext(filename)
        mp4_path = base + ".mp4"
        if os.path.exists(mp4_path):
            print(f"[video] Đã tải: {mp4_path}")
            return mp4_path
        elif os.path.exists(filename):
            print(f"[video] Đã tải: {filename}")
            return filename
        else:
            print(f"[video] Không tìm thấy file sau khi tải: {filename}")
            return None
    except Exception as e:
        print(f"[video] Lỗi tải {url}: {e}")
        return None


def download_one(
    item: dict,
    videos_dir: str,
    images_dir: str,
    ffmpeg_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> Optional[str]:
    """
    Tải 1 item từ danh sách Sheet.
    Trả về đường dẫn file, hoặc None nếu lỗi.
    """
    link = item.get("link", "").strip()
    kind = item.get("type", "").strip().lower()

    if not link:
        print("[download] Bỏ qua item không có link")
        return None

    print(f"\n[download] Xử lý: {link} (type={kind})")

    if kind == "image":
        return download_image(link, images_dir, skip_if_exists=skip_if_exists)

    # Tự phát hiện nếu type trống hoặc không rõ
    if kind in ("youtube", "tiktok", "video") or _is_youtube(link) or _is_tiktok(link):
        return download_video(
            link, videos_dir,
            ffmpeg_path=ffmpeg_path,
            skip_if_exists=skip_if_exists,
        )

    print(f"[download] Loại không hỗ trợ: {kind}")
    return None


def download_all(
    items: list,
    videos_dir: str,
    images_dir: str,
    ffmpeg_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> list:
    """
    Tải tất cả item trong danh sách.
    Trả về list các dict: [{"item": ..., "path": ..., "ok": True/False}, ...]
    """
    results = []
    total = len(items)

    for i, item in enumerate(items, 1):
        print(f"\n===== [{i}/{total}] =====")
        path = download_one(
            item, videos_dir, images_dir,
            ffmpeg_path=ffmpeg_path,
            skip_if_exists=skip_if_exists,
        )
        results.append({
            "item": item,
            "path": path,
            "ok": path is not None,
        })

    # Tổng kết
    ok_count = sum(1 for r in results if r["ok"])
    print(f"\n===== TỔNG KẾT: {ok_count}/{total} tải thành công =====")

    return results


if __name__ == "__main__":
    import yaml
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from backend.sheet_reader import read_sheet

    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Đọc Sheet
    gs = cfg["google_sheet"]
    items = read_sheet(gs["sheet_id"], gs["credentials_file"], gs["tab_name"])
    print(f"Đọc được {len(items)} item từ Sheet\n")

    # Tải về
    results = download_all(
        items,
        videos_dir=cfg["paths"]["videos_dir"],
        images_dir=cfg["paths"]["images_dir"],
        ffmpeg_path=cfg["ffmpeg"]["path"],
        skip_if_exists=cfg["downloader"]["skip_if_exists"],
    )

    # In chi tiết
    print("\n===== CHI TIẾT =====")
    for r in results:
        status = "✅" if r["ok"] else "❌"
        print(f"{status} {r['item']['link']} → {r['path']}")