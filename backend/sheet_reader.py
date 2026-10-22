"""Bước 1: Đọc danh sách link từ Google Sheet."""
import os
from typing import List, Dict, Optional

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_client(credentials_file: str) -> gspread.Client:
    """Tạo gspread client từ file Service Account JSON."""
    if not os.path.exists(credentials_file):
        raise FileNotFoundError(
            f"Không tìm thấy file credentials: {credentials_file}\n"
            f"Xem hướng dẫn tạo Service Account trong README."
        )
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    return gspread.authorize(creds)


def read_sheet(
    sheet_id: str,
    credentials_file: str,
    tab_name: str = "Sheet1",
    skip_empty_link: bool = True,
) -> List[Dict]:
    """
    Đọc Google Sheet, trả về list các dict.

    Sheet cần có header (dòng 1):
        link | type | topic | date

    Mỗi dòng dữ liệu trả về dạng:
        {"link": "...", "type": "youtube", "topic": "...", "date": "..."}
    """
    client = _get_client(credentials_file)
    sheet = client.open_by_key(sheet_id).worksheet(tab_name)

    rows = sheet.get_all_records()  # Trả về list các dict với header làm key

    results = []
    for idx, row in enumerate(rows, start=2):  # Dòng 2 là dòng dữ liệu đầu tiên
        link = str(row.get("link", "")).strip()
        if not link:
            if skip_empty_link:
                continue

        item = {
            "row": idx,
            "link": link,
            "type": str(row.get("type", "")).strip().lower(),
            "topic": str(row.get("topic", "")).strip(),
            "date": str(row.get("date", "")).strip(),
        }
        results.append(item)

    return results


def group_by_topic(items: List[Dict]) -> Dict[str, List[Dict]]:
    """Nhóm các item theo topic — dùng cho bước ghép video."""
    groups: Dict[str, List[Dict]] = {}
    for item in items:
        topic = item.get("topic") or "uncategorized"
        groups.setdefault(topic, []).append(item)
    return groups


def filter_by_type(items: List[Dict], kind: str) -> List[Dict]:
    """Lọc theo loại: youtube | tiktok | image."""
    return [i for i in items if i.get("type") == kind]


if __name__ == "__main__":
    # Test nhanh
    import yaml

    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    gs = cfg["google_sheet"]
    rows = read_sheet(gs["sheet_id"], gs["credentials_file"], gs["tab_name"])

    print(f"Tổng số link: {len(rows)}")
    for r in rows[:5]:
        print(r)

    print("\nTheo topic:")
    for topic, items in group_by_topic(rows).items():
        print(f"  {topic}: {len(items)} link")