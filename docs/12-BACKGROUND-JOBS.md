# 12 — Background Jobs

## Overview

InfoStore has two background processing systems that run alongside the HTTP server:

1. **File Watchdog** — Monitors directories for new files and queues them for processing
2. **Watchdog Consumer** — Background asyncio task that drains the file queue

Both are managed within FastAPI's `lifespan` context manager in `main.py`.

---

## Architecture

```
File System
    │
    │ (new file created)
    ▼
InfoStoreHandler.on_created()       [watchdog library, runs in watchdog thread]
    │
    │ asyncio.run_coroutine_threadsafe(file_queue.put(path), event_loop)
    ▼
asyncio.Queue[str]  (file_queue)    [shared between watchdog thread and consumer]
    │
    │ await file_queue.get()
    ▼
watchdog_consumer()                 [asyncio task, runs in event loop]
    │
    │ loop.run_in_executor(executor, _process_file_sync, path)
    ▼
ThreadPoolExecutor                  [max_workers=2]
    │
    │ (runs synchronously on thread)
    ▼
_process_file_sync(path)
    └── _process_image(path)   OR   _process_document(path)
            └── _process_and_store(text, source_type, source)
```

---

## File Watchdog (`ingestion/watchdog_agent.py`)

### The `watchdog` Library

Uses the Python `watchdog` library, which hooks into native OS file system events:
- **Windows:** ReadDirectoryChangesW API
- **Linux:** inotify
- **macOS:** FSEvents or kqueue

This is more efficient than polling — no CPU burn scanning directories repeatedly.

### `InfoStoreHandler` Class

```python
class InfoStoreHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
    
    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        
        path = event.src_path
        if not (is_image_file(path) or is_document_file(path)):
            return
        
        # Thread-safe queue put from watchdog's thread into async event loop
        asyncio.run_coroutine_threadsafe(
            file_queue.put(path),
            self._loop
        )
        logger.info(f"Queued new file: {path}")
    
    def on_modified(self, event: FileModifiedEvent):
        # Same handler — re-queue modified files for re-indexing
        self.on_created(event)
```

### Supported Extensions

```python
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

def is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS

def is_document_file(path: str) -> bool:
    return Path(path).suffix.lower() in DOCUMENT_EXTENSIONS
```

### Starting the Watchdog

```python
_observer: Observer | None = None

def start_watchdog(dirs: list[str]):
    global _observer
    loop = asyncio.get_event_loop()
    handler = InfoStoreHandler(loop)
    
    _observer = Observer()
    for d in dirs:
        path = Path(d.strip()).expanduser()
        if path.exists():
            _observer.schedule(handler, str(path), recursive=True)
            logger.info(f"Watching: {path}")
    
    _observer.start()
    
    # Pre-queue existing files that haven't been indexed yet
    for d in dirs:
        path = Path(d.strip()).expanduser()
        if path.exists():
            for f in path.rglob("*"):
                if f.is_file() and (is_image_file(str(f)) or is_document_file(str(f))):
                    if not is_source_indexed(str(f)):
                        file_queue.put_nowait(str(f))
                        logger.debug(f"Pre-queued existing file: {f}")
```

### Stopping the Watchdog

```python
def stop_watchdog():
    global _observer
    if _observer and _observer.is_alive():
        _observer.stop()
        _observer.join()
        _observer = None
```

---

## Watchdog Consumer (`main.py`)

The consumer is an asyncio coroutine that runs as a background task for the entire lifetime of the FastAPI server.

```python
async def watchdog_consumer():
    """Drain the file queue, processing one file at a time with thread pool."""
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_event_loop()
    
    logger.info("Watchdog consumer started")
    
    while True:
        try:
            path = await file_queue.get()        # Blocks until item available
            logger.info(f"Processing queued file: {path}")
            
            # Run blocking ML operations in thread pool (non-blocking for event loop)
            await loop.run_in_executor(
                executor,
                _process_file_sync,
                path
            )
            
            file_queue.task_done()               # Signals queue item is complete
        except asyncio.CancelledError:
            logger.info("Watchdog consumer cancelled")
            break
        except Exception as e:
            logger.error(f"Consumer error for {path}: {e}")
            file_queue.task_done()               # Prevent queue from getting stuck
```

### Thread Pool
`ThreadPoolExecutor(max_workers=2)` — at most 2 files are processed simultaneously. This prevents overwhelming the GPU/CPU with concurrent ML inference.

### Error Handling
Even if `_process_file_sync` raises an exception, `task_done()` is called in the `except` block. Without this, `file_queue.join()` would hang forever (if it's ever called).

---

## File Processing (`_process_file_sync` in `router.py`)

```python
def _process_file_sync(path: str):
    """Synchronous file processing — called from thread pool."""
    try:
        path = Path(path)
        if not path.exists():
            logger.warning(f"File no longer exists: {path}")
            return
        
        # Skip already-indexed files (idempotency)
        if is_source_indexed(str(path)):
            logger.info(f"Already indexed, skipping: {path}")
            return
        
        if is_image_file(str(path)):
            text, source_type = _process_image(str(path))
        elif is_document_file(str(path)):
            text = document_parser.parse_document(str(path))
            source_type = "document"
        else:
            return
        
        if not text or not text.strip():
            logger.warning(f"No text extracted from: {path}")
            return
        
        _process_and_store(text, source_type, str(path), tags=[])
        logger.info(f"Successfully indexed: {path}")
    except Exception as e:
        logger.error(f"Failed to process {path}: {e}", exc_info=True)
```

---

## Bookmark Sync

Bookmark sync is **on-demand** (not continuous). It runs when the user clicks "Sync Bookmarks" in the UI, which calls `POST /api/bookmarks/sync`.

```python
@router.post("/bookmarks/sync")
async def sync_bookmarks(req: BookmarkSyncRequest, background_tasks: BackgroundTasks):
    """Start bookmark sync as a background task so the HTTP response is immediate."""
    background_tasks.add_task(
        _sync_bookmarks_task,
        req.bookmark_path or settings.bookmark_path,
        req.max_bookmarks
    )
    return {"message": "Bookmark sync started", "status": "running"}

async def _sync_bookmarks_task(bookmark_path: str, max_bookmarks: int):
    bookmarks = bookmark_sync.parse_chrome_bookmarks(bookmark_path)
    
    synced = skipped = failed = 0
    for bm in bookmarks[:max_bookmarks]:
        url = bm["url"]
        if is_source_indexed(url):
            skipped += 1
            continue
        try:
            text = await asyncio.to_thread(web_scraper.extract_from_url, url)
            await asyncio.to_thread(_process_and_store, text, "bookmark", url, tags=[])
            synced += 1
        except Exception as e:
            logger.warning(f"Bookmark sync failed for {url}: {e}")
            failed += 1
    
    logger.info(f"Bookmark sync complete: {synced} synced, {skipped} skipped, {failed} failed")
```

### Deduplication
`is_source_indexed(url)` queries ChromaDB for any entry with `source == url`. If found, the bookmark is skipped. This makes sync **idempotent** — running it multiple times is safe.

---

## Force Re-index

The `/api/watchdog/force-reindex` endpoint provides a way to clear and rebuild the entire index:

```python
@router.post("/watchdog/force-reindex")
async def force_reindex():
    """Delete all existing chunks and re-queue everything."""
    dirs = settings.watch_dirs.split(",") if settings.watch_dirs else []
    
    deleted_total = 0
    queued_total = 0
    
    for dir_path in dirs:
        path = Path(dir_path.strip()).expanduser()
        if not path.exists():
            continue
        
        for f in path.rglob("*"):
            if f.is_file() and (is_image_file(str(f)) or is_document_file(str(f))):
                # Delete existing chunks for this source
                deleted = delete_by_source(str(f))
                deleted_total += deleted
                
                # Re-queue for fresh indexing
                file_queue.put_nowait(str(f))
                queued_total += 1
    
    return {
        "deleted_chunks": deleted_total,
        "queued": queued_total,
        "message": f"Cleared {deleted_total} chunks, queued {queued_total} files"
    }
```

This is destructive and cannot be undone. Use when:
- Chunking parameters have changed (`CHUNK_SIZE`, `CHUNK_OVERLAP`)
- You want to re-run with contextual retrieval enabled
- Index has become stale due to schema changes

---

## Lifespan Management (`main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP ===
    logger.info("InfoStore starting up...")
    
    # Start watchdog file consumer
    consumer_task = asyncio.create_task(watchdog_consumer())
    
    # Warm up Ollama (pre-load model into memory)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _warmup_ollama)
    
    # Auto-start file watchdog if dirs configured
    if settings.watch_dirs:
        dirs = [d.strip() for d in settings.watch_dirs.split(",") if d.strip()]
        start_watchdog(dirs)
        logger.info(f"Auto-started watchdog on {len(dirs)} directories")
    
    yield   # Server is now running
    
    # === SHUTDOWN ===
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    
    stop_watchdog()
    logger.info("InfoStore shutdown complete")
```

---

## Queue Monitoring

Current queue state is not exposed via API (no `/queue/status` endpoint). To monitor:
- Check `backend/logs/watchdog_agent.log` for "Queued new file" messages
- Check `backend/logs/api_router.log` for "Successfully indexed" messages
- Call `GET /api/stats` and watch `total_documents` increase over time
