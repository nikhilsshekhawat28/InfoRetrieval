# 13 — Error Handling and Logging

## Logging Architecture

### Logger Factory (`app/utils/logger.py`)

Every module creates its own logger via `get_logger(name)`:

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

def get_logger(name: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(f"infostore.{name}")
    
    if logger.handlers:
        return logger  # Avoid duplicate handlers on re-import
    
    logger.setLevel(logging.DEBUG)
    
    # Rotating file handler: 5MB max, keep 3 backups
    file_handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=5 * 1024 * 1024,   # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False   # Don't bubble up to root logger
    
    return logger
```

### Log Files

| File | Module | What's Logged |
|------|--------|---------------|
| `main.log` | `main.py` | Server start/stop, consumer task lifecycle |
| `api_router.log` | `router.py` | Request handling, ingestion results, bookmark sync progress |
| `rag_pipeline.log` | `rag_pipeline.py` | Query routing decisions, CRAG triggers, answer generation |
| `vector_store.log` | `vector_store.py` | ChromaDB operations, chunk counts, search results |
| `chunker.log` | `chunker.py` | Chunking stats (word count → chunk count) |
| `summarizer.log` | `summarizer.py` | Summarization performance, truncation events |
| `embedder.log` | `embedder.py` | Batch embedding sizes |
| `reranker.log` | `reranker.py` | Reranking score distributions |
| `image_captioning.log` | `image_captioning.py` | Caption generation, model loading |
| `ocr_pipeline.log` | `ocr_pipeline.py` | OCR method used, text length |
| `document_parser.log` | `document_parser.py` | File parse events, page counts |
| `tagger.log` | `tagger.py` | Generated tags per document |
| `web_scraper.log` | `web_scraper.py` | Scraping method, text length, skipped URLs |
| `bookmark_sync.log` | `bookmark_sync.py` | Bookmark count, sync progress |
| `watchdog_agent.log` | `watchdog_agent.py` | Detected files, queue puts |

### Log Rotation
- Each log file: max 5MB
- 3 backup files kept (`.log.1`, `.log.2`, `.log.3`)
- Total max per module: 20MB

---

## Error Handling Strategies

### 1. Extraction Failures

Extraction errors are caught at the router level:

```python
@router.post("/store/url")
async def store_url(req: StoreURLRequest):
    try:
        text = web_scraper.extract_from_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # e.g., login URL
    except Exception as e:
        logger.error(f"Scraping failed for {req.url}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract content: {e}")
```

### 2. Model Failures

ML model calls are wrapped with fallback logic:

**Summarizer fallback:**
```python
def summarize(text: str) -> str:
    try:
        return _run_t5_summarization(text)
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # Fallback: return first 150 chars
        return text[:150].strip() + "..."
```

**Ollama fallback chain:**
```python
def answer_query(query: str, ...) -> dict:
    try:
        answer = _query_ollama(prompt, context)
    except Exception as e:
        logger.warning(f"Ollama failed ({e}), falling back to T5")
        try:
            answer = _query_t5(prompt)
        except Exception as e2:
            logger.error(f"T5 also failed ({e2}), using context concatenation")
            answer = " ".join(r["summary"] for r in results[:3])
```

### 3. ChromaDB Errors

ChromaDB operations are wrapped defensively:

```python
def is_source_indexed(source: str) -> bool:
    try:
        results = collection.get(where={"source": source}, limit=1, include=[])
        return len(results["ids"]) > 0
    except Exception as e:
        logger.warning(f"Could not check index status for {source}: {e}")
        return False   # Fail open: allow re-indexing rather than blocking
```

```python
def get_sibling_chunks(doc_id: str, window: int = 1) -> list[str]:
    try:
        # ... ChromaDB queries ...
    except Exception as e:
        logger.error(f"Sibling chunk retrieval error: {e}")
        return []   # Degrade gracefully: answer without sibling context
```

### 4. Web Scraping Failures

The scraper has a two-level fallback:

```python
def extract_from_url(url: str) -> str:
    # Level 0: URL validation
    for skip_pattern in ["login", "signin", "mail", "oauth"]:
        if skip_pattern in url.lower():
            raise ValueError(f"Skipping auth URL: {url}")
    
    # Level 1: Trafilatura (fast)
    try:
        text = scrape_with_trafilatura(url)
        if text and len(text) >= 50:
            return text
    except Exception as e:
        logger.warning(f"Trafilatura failed for {url}: {e}")
    
    # Level 2: Playwright (JS-heavy pages)
    try:
        return asyncio.run(scrape_with_playwright(url))
    except Exception as e:
        logger.error(f"Playwright also failed for {url}: {e}")
        raise RuntimeError(f"Could not extract content from {url}")
```

### 5. Watchdog Consumer Errors

The consumer catches per-file errors to prevent queue stalls:

```python
async def watchdog_consumer():
    while True:
        path = await file_queue.get()
        try:
            await loop.run_in_executor(executor, _process_file_sync, path)
        except Exception as e:
            logger.error(f"Consumer error for {path}: {e}", exc_info=True)
        finally:
            file_queue.task_done()  # ALWAYS called, even on error
```

### 6. HTTP Error Responses

FastAPI automatically converts unhandled exceptions to 500 responses. The API raises explicit `HTTPException` for known error conditions:

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Invalid input | Login-only URL, empty text |
| 404 | Not found | `DELETE /entry/{nonexistent_id}` |
| 422 | Validation failure | Missing required field, wrong type |
| 500 | Unexpected server error | Model crash, file system error |

---

## Observability

### Health Check
```
GET /health → {"status": "ok", "version": "2.0"}
```
Useful for Docker health checks and monitoring scripts.

### Stats Endpoint
```
GET /api/stats → total_documents, by_type, file_counts...
```
Frontend polls this every 30 seconds to show live counts.

### Log Tailing (Development)
```bash
# Watch all logs in real-time
tail -f backend/logs/*.log

# Just the RAG pipeline
tail -f backend/logs/rag_pipeline.log

# Just errors
grep -i "error\|exception" backend/logs/api_router.log
```

---

## Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused: localhost:11434` | Ollama not running | Run `ollama serve` |
| `Model not found: granite3.1-dense:2b` | Model not pulled | Run `ollama pull granite3.1-dense:2b` |
| `CUDA out of memory` | GPU VRAM exhausted | Set `DEVICE_PREFERENCE=cpu` or reduce batch sizes |
| `FileNotFoundError: Bookmarks` | Wrong bookmark path | Check `BOOKMARK_PATH` in `.env` |
| `Port 8000 already in use` | Old server process still running | Kill old process: `taskkill /F /IM python.exe` (Windows) |
| `ChromaDB collection has no documents` | Watch dirs empty or not started | Click "Sync Bookmarks" or add files to `watch_data/` |
| `playwright._impl._errors.Error: Chromium not found` | Playwright browsers not installed | Run `playwright install chromium` |
| `EasyOCR download error` | First run, models not cached | EasyOCR downloads models on first use (~500MB) |
