# 05 — API Routes

**Base URL:** `http://localhost:8000/api`  
**Format:** All requests and responses use `application/json` unless noted.  
**CORS:** Allowed origin: `http://localhost:5173` (frontend dev server)

---

## Health

### `GET /health`
Returns server status.

**Response:**
```json
{
  "status": "ok",
  "version": "2.0"
}
```

---

## Statistics

### `GET /stats`
Returns collection statistics including document counts, type breakdowns, and file system counts.

**Response:**
```json
{
  "total_documents": 1247,
  "total_chunks": 1198,
  "unique_parents": 32,
  "collection_name": "info_store",
  "by_type": {
    "document": 980,
    "image_caption": 120,
    "image_ocr": 47,
    "url": 40,
    "text": 30,
    "bookmark": 30
  },
  "file_counts": {
    "images_on_disk": 4,
    "documents_on_disk": 27,
    "bookmarks": 312
  }
}
```

---

## Ingestion: URL

### `POST /store/url`
Scrape a URL and add its content to the knowledge base.

**Request:**
```json
{
  "url": "https://en.wikipedia.org/wiki/Formula_One",
  "tags": ["f1", "wikipedia"]
}
```

**Process:**
1. `web_scraper.extract_from_url(url)` → text
2. `_process_and_store(text, "url", url, tags)`

**Response:**
```json
{
  "id": ["uuid-chunk-0", "uuid-chunk-1", "..."],
  "summary": "Formula One is the highest class of international open-wheel single-seater...",
  "source_type": "url",
  "tags": ["formula one", "racing", "motorsport", "f1"],
  "chunk_count": 8,
  "message": "success"
}
```

**Errors:**
- `400` if URL is a login/mail page
- `422` if URL is malformed

---

## Ingestion: Text Note

### `POST /store/text`
Store a text note directly.

**Request:**
```json
{
  "text": "Mercedes uses a nose-mounted DRS actuator...",
  "title": "My F1 Notes",
  "tags": ["notes", "mercedes"]
}
```

**Response:** Same shape as `/store/url` with `source_type: "text"`.

---

## Ingestion: File Upload

### `POST /store/file`
Upload a file (image or document) for processing.

**Request:** `multipart/form-data`
- `file`: Binary file data
- `tags`: Optional JSON array string, e.g. `'["tag1","tag2"]'`

**Smart routing:**
- Images (jpg/png/gif/bmp/webp): `ocr_pipeline.run_ocr()` + `image_captioning.generate_caption()`
  - If OCR text ≥ 20 chars: stored as `"image_ocr"`
  - Otherwise: stored as `"image_caption"`
- Documents (pdf/docx/txt/md): `document_parser.parse_document()` → stored as `"document"`

**Response:** Same `IngestResponse` shape.

---

## Ingestion: Local Path

### `POST /store/path`
Process a file at a local path (used internally by watchdog).

**Request:**
```json
{
  "file_path": "/absolute/path/to/file.pdf",
  "tags": []
}
```

---

## Search

### `POST /search`
Semantic + keyword hybrid search without LLM answer generation.

**Request:**
```json
{
  "query": "DRS overtaking mechanics",
  "top_k": 5,
  "source_type": "document"
}
```

**Process:**
1. Embed query (BGE)
2. Hybrid search (RRF)
3. Cross-encoder rerank
4. Return top_k results

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "summary": "DRS (Drag Reduction System) allows...",
      "chunk_text": "The DRS zone opens when a driver...",
      "source_type": "document",
      "source": "/path/to/file.pdf",
      "tags": ["drs", "formula 1", "aerodynamics"],
      "distance": 0.12,
      "rerank_score": 4.32,
      "rrf_score": 0.031,
      "parent_id": "uuid-parent",
      "chunk_index": 3
    }
  ],
  "query": "DRS overtaking mechanics",
  "total": 5
}
```

---

## Chat (RAG)

### `POST /chat`
Ask a question. The system retrieves relevant context and generates an answer.

**Request:**
```json
{
  "query": "How does KERS work in Formula 1?",
  "top_k": 5,
  "evaluate": false
}
```

**Full pipeline:** See [03-ARCHITECTURE.md](./03-ARCHITECTURE.md) § Data Flow: Full Query Cycle

**Response:**
```json
{
  "answer": "KERS (Kinetic Energy Recovery System) captures braking energy and stores it in a battery or flywheel, then releases it as a power boost...",
  "sources": [ /* StoredItem[] */ ],
  "crag_triggered": false,
  "query_rewritten": null,
  "evaluation": null
}
```

**With evaluation=true:**
```json
{
  "answer": "...",
  "sources": [...],
  "crag_triggered": false,
  "evaluation": {
    "faithfulness": 0.92,
    "answer_relevancy": 0.88,
    "context_precision": 0.79,
    "overall": 0.86
  }
}
```

---

## Bookmarks

### `GET /bookmarks/preview`
Preview Chrome bookmarks without syncing.

**Response:**
```json
{
  "bookmarks": [
    {
      "url": "https://example.com",
      "title": "Example Site",
      "folder": "Bookmarks Bar",
      "date_added": 1712000000
    }
  ],
  "total": 312,
  "new": 45,
  "already_indexed": 267
}
```

### `POST /bookmarks/sync`
Ingest new (not yet indexed) bookmarks.

**Request:**
```json
{
  "bookmark_path": null,
  "max_bookmarks": 500
}
```

**Process:**
1. Parse Chrome Bookmarks JSON
2. For each bookmark URL: check `is_source_indexed(url)`
3. If new: `web_scraper.extract_from_url(url)` → `_process_and_store()`
4. Track synced/skipped/failed counts

**Response:**
```json
{
  "synced": 45,
  "skipped": 267,
  "failed": 3,
  "message": "Bookmark sync complete"
}
```

### `GET /bookmarks/status`
Check sync progress during a running sync.

**Response:**
```json
{
  "syncing": true,
  "synced": 12,
  "total": 45,
  "current_url": "https://example.com/article"
}
```

---

## Watchdog

### `POST /watchdog/start`
Start file system monitoring on configured directories.

**Request:**
```json
{
  "watch_dirs": [
    "E:/NEU/Sem 2/APP/Project/proj jsr/watch_data/documents",
    "E:/NEU/Sem 2/APP/Project/proj jsr/watch_data/images"
  ]
}
```

**Response:**
```json
{
  "status": "started",
  "watching": 2,
  "message": "Watchdog monitoring 2 directories"
}
```

### `POST /watchdog/stop`
Stop file system monitoring.

**Response:**
```json
{ "status": "stopped" }
```

### `POST /watchdog/reindex`
Scan watch directories and queue new (not yet indexed) files.

**Response:**
```json
{
  "queued": 5,
  "skipped": 26,
  "message": "5 new files queued for indexing"
}
```

### `POST /watchdog/force-reindex`
Delete all existing chunks and re-index everything from scratch.

**Warning:** This is destructive — all existing chunks are deleted.

**Process:**
1. For each file in watch directories: `delete_by_source(path)`
2. Re-queue all files via `file_queue.put(path)`

**Response:**
```json
{
  "deleted_chunks": 968,
  "queued": 31,
  "message": "Cleared 968 chunks, queued 31 files for re-indexing"
}
```

---

## Entry Management

### `DELETE /entry/{doc_id}`
Delete a document entry. If it's a chunked document, all sibling chunks are deleted.

**Path parameter:** `doc_id` — UUID of any chunk belonging to the document

**Process:**
1. Get metadata for `doc_id`
2. If has `parent_id`: delete all chunks with same parent_id
3. Otherwise: delete the single entry

**Response:**
```json
{ "deleted": true, "doc_id": "uuid" }
```

---

## Evaluation

### `POST /evaluate`
Same as `/chat` but forces RAGAS evaluation regardless of `evaluate` flag.

**Request:** Same as `ChatRequest`  
**Response:** Same as `ChatResponse` but `evaluation` is always populated.

---

## Error Responses

All errors follow FastAPI's default format:

```json
{
  "detail": "Error description string"
}
```

Common status codes:
- `400 Bad Request` — Invalid input (e.g., login-only URL, empty text)
- `404 Not Found` — `DELETE /entry/{id}` for non-existent ID
- `422 Unprocessable Entity` — Pydantic validation failure
- `500 Internal Server Error` — Unexpected processing failure

---

## OpenAPI Documentation

When the backend is running, interactive API docs are available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
