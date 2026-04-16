import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from app.utils.logger import get_logger

logger = get_logger("watchdog_agent")

# Supported file extensions
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md"}
SUPPORTED_EXTS = IMAGE_EXTS | DOC_EXTS

# Queue for new files detected by the watchdog
file_queue: asyncio.Queue = asyncio.Queue()


class InfoStoreHandler(FileSystemEventHandler):
    """Handles new file creation events in watched directories."""

    def on_created(self, event):
        if event.is_directory:
            return
        if not isinstance(event, FileCreatedEvent):
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTS:
            return

        logger.info(f"New file detected: {path}")
        try:
            file_queue.put_nowait(str(path))
        except asyncio.QueueFull:
            logger.warning("File queue full, dropping event")


_observer = None


def start_watchdog(directories: list[str]) -> bool:
    """Start watching directories for new files."""
    global _observer

    if _observer is not None:
        logger.warning("Watchdog already running")
        return False

    _observer = Observer()
    handler = InfoStoreHandler()

    watched = 0
    for dir_path in directories:
        path = Path(dir_path).expanduser()
        if path.exists() and path.is_dir():
            _observer.schedule(handler, str(path), recursive=True)
            logger.info(f"Watching directory: {path}")
            watched += 1
        else:
            logger.warning(f"Directory not found: {path}")

    if watched == 0:
        logger.error("No valid directories to watch")
        return False

    _observer.start()
    logger.info(f"Watchdog started, monitoring {watched} directories")

    # Enqueue files that already exist in the watched directories
    queued = 0
    for dir_path in directories:
        path = Path(dir_path).expanduser()
        if path.exists() and path.is_dir():
            for file in path.rglob("*"):
                if file.is_file() and file.suffix.lower() in SUPPORTED_EXTS:
                    try:
                        file_queue.put_nowait(str(file))
                        queued += 1
                    except asyncio.QueueFull:
                        logger.warning(f"Queue full, skipping existing file: {file}")
    if queued:
        logger.info(f"Queued {queued} existing files for processing")

    return True


def stop_watchdog():
    """Stop the file system watchdog."""
    global _observer
    if _observer is not None:
        _observer.stop()
        _observer.join()
        _observer = None
        logger.info("Watchdog stopped")


def is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def is_document_file(path: str) -> bool:
    return Path(path).suffix.lower() in DOC_EXTS
