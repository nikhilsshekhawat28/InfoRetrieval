import json
from pathlib import Path
from datetime import datetime
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("bookmark_sync")


def parse_chrome_bookmarks(bookmark_path: str | None = None) -> list[dict]:
    """
    Parse Chrome Bookmarks JSON file and extract all bookmark URLs.
    Returns list of {url, title, date_added, folder}.
    """
    path = bookmark_path or settings.bookmark_path
    path = Path(path).expanduser()

    if not path.exists():
        logger.warning(f"Bookmark file not found: {path}")
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read bookmarks file: {e}")
        return []

    bookmarks = []
    _extract_bookmarks(data.get("roots", {}), bookmarks, folder="")
    logger.info(f"Parsed {len(bookmarks)} bookmarks from {path}")
    return bookmarks


def _extract_bookmarks(node: dict, bookmarks: list, folder: str):
    """Recursively extract bookmarks from Chrome JSON structure."""
    if isinstance(node, dict):
        if node.get("type") == "url":
            url = node.get("url", "")
            if url.startswith("http"):
                # Chrome stores timestamps as microseconds since 1601-01-01
                date_added = node.get("date_added", "")
                try:
                    ts = int(date_added)
                    # Convert Chrome epoch to Unix epoch
                    unix_ts = (ts - 11644473600000000) / 1000000
                    date_str = datetime.fromtimestamp(unix_ts).isoformat()
                except (ValueError, OSError):
                    date_str = ""

                bookmarks.append({
                    "url": url,
                    "title": node.get("name", ""),
                    "date_added": date_str,
                    "folder": folder,
                })
        elif node.get("type") == "folder":
            child_folder = f"{folder}/{node.get('name', '')}" if folder else node.get("name", "")
            for child in node.get("children", []):
                _extract_bookmarks(child, bookmarks, child_folder)
        else:
            # Root-level keys like "bookmark_bar", "other", "synced"
            for key, value in node.items():
                if isinstance(value, dict):
                    _extract_bookmarks(value, bookmarks, folder)
