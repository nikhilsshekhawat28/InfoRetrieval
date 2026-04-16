# 03 — Architecture

## High-Level Overview

InfoStore v2 follows a **client-server architecture** with a clear separation of concerns:

- **Frontend** (React): UI-only, no business logic; all AI/ML work happens on the backend
- **Backend** (FastAPI): Orchestrates ingestion, processing, storage, retrieval, and generation
- **ChromaDB**: Local persistent vector database
- **Ollama**: Local LLM inference server (separate process)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser (:5173)                                                     │
│  React + Vite + Tailwind                                            │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  AppSidebar   │  │  ChatInput   │  │  ChatMessage / Sources  │  │
│  │  (ingestion)  │  │  (query)     │  │  (answers + metadata)   │  │
│  └───────────────┘  └──────────────┘  └─────────────────────────┘  │
│          │                  │                                        │
│          └──────────────────┼──────────── api.ts (fetch)           │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ HTTP REST (JSON)
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│  FastAPI Backend (:8000)                                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ingestion/router.py  (all /api/* routes)                   │   │
│  └──────┬────────────────────────────────────────┬─────────────┘   │
│         │ ingestion flow                          │ query flow      │
│  ┌──────▼─────────────┐               ┌──────────▼──────────────┐  │
│  │  EXTRACTION LAYER  │               │  RETRIEVAL LAYER        │  │
│  │  document_parser   │               │  rag_pipeline.py        │  │
│  │  image_captioning  │               │    - query routing      │  │
│  │  ocr_pipeline      │               │    - hybrid search      │  │
│  │  web_scraper       │               │    - reranking          │  │
│  └──────┬─────────────┘               │    - CRAG               │  │
│         │                             │    - generation         │  │
│  ┌──────▼─────────────┐               └──────────┬──────────────┘  │
│  │  PROCESSING LAYER  │                          │                  │
│  │  summarizer        │               ┌──────────▼──────────────┐  │
│  │  tagger            │               │  evaluator.py           │  │
│  │  chunker           │               │  (RAGAS metrics)        │  │
│  │  embedder          │               └─────────────────────────┘  │
│  └──────┬─────────────┘                                            │
│         │                                                           │
│  ┌──────▼─────────────┐                                            │
│  │  STORAGE LAYER     │◄──────────────────────────────────────┐   │
│  │  vector_store.py   │                                        │   │
│  │  (ChromaDB ops)    │                                        │   │
│  └──────┬─────────────┘                                        │   │
│         │                                                       │   │
│  ┌──────▼─────────────┐    ┌──────────────────────────────┐    │   │
│  │  ChromaDB          │    │  Ollama (:11434)              │    │   │
│  │  chroma_data/      │    │  granite3.1-dense:2b          │────┘   │
│  │  cosine similarity │    │  local inference              │        │
│  └────────────────────┘    └──────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Layers

### 1. Ingestion Layer

Responsible for getting content into the system. Orchestrated by `ingestion/router.py`.

```
Input Sources
     │
     ├── URL          → web_scraper.py → text
     ├── Document     → document_parser.py → text
     ├── Image        → ocr_pipeline.py + image_captioning.py → text + caption
     ├── Text Note    → direct string
     ├── Bookmark     → bookmark_sync.py → URL list → web_scraper
     └── File System  → watchdog_agent.py → file path → appropriate extractor

text
  │
  ▼
_process_and_store()   [in router.py]
  │
  ├─ summarizer.py     → human-readable summary
  ├─ tagger.py         → topic tags list
  ├─ chunker.py        → overlapping sentence-boundary chunks[]
  ├─ (optional) _contextualize_chunk() → adds LLM context prefix per chunk
  ├─ embedder.py       → embeddings[] (one per chunk)
  └─ vector_store.add_chunks() → stored in ChromaDB
```

### 2. Processing Layer

Transforms raw extracted text into indexed, searchable form.

| Module | Input | Output | Key Detail |
|--------|-------|--------|------------|
| `summarizer.py` | raw text | 1-sentence summary | T5 fine-tuned, beam search, repetition penalty |
| `tagger.py` | raw text | tags list | T5 with comma-split parsing |
| `chunker.py` | raw text | chunks[] | sentence-boundary, 300w/80w overlap |
| `embedder.py` | text or chunks[] | float[768] or list | BGE-base, L2-normalized |

### 3. Storage Layer

Single module: `storage/vector_store.py`. All ChromaDB interactions abstracted.

```
ChromaDB Collection: "info_store"
  Metric: cosine similarity
  
  Per document chunk stored:
    id:         UUID (string)
    embedding:  float[768]  (BGE)
    document:   chunk text
    metadata:
      source_type:     "document" | "url" | "image_caption" | "image_ocr" | "text" | "bookmark"
      source:          file path or URL
      tags:            JSON array string
      created_at:      ISO timestamp
      parent_id:       UUID (shared by all chunks of one document)
      chunk_index:     int (0-based position)
      total_chunks:    int
      summary:         truncated T5 summary (max 1000 chars)
      full_text_length: int
```

### 4. Retrieval Layer

The RAG pipeline. Entry point: `retrieval/rag_pipeline.py → answer_query()`.

```
Query String
    │
    ├─ _is_conversational()? ──Yes──→ Ollama direct chat (no KB)
    │
    ├─ _is_weather_query()?  ──Yes──→ _fetch_weather() → wttr.in API
    │                                  → Ollama formats response
    │
    └─ Otherwise:
         │
         ├─ kb_query = _is_kb_query(query)
         ├─ embedder.embed_text(query)
         ├─ vector_store.hybrid_search()   [RRF dense+keyword]
         ├─ _deduplicate_by_source()       [max 2 chunks per source]
         ├─ reranker.rerank()              [cross-encoder scoring]
         ├─ max_rerank_score evaluation
         │
         ├─ if score < 2.5 AND NOT domain_query AND NOT kb_query:
         │       → _answer_without_context()  [web search / LLM only]
         │
         ├─ if score < 2.5 AND kb_query:
         │       → "I searched but couldn't find..." message
         │
         └─ Otherwise (good retrieval):
               │
               ├─ _evaluate_retrieval_quality() → "good"/"marginal"/"poor"
               ├─ if "poor": _rewrite_query() → CRAG re-retrieval
               ├─ build_context() → expand with sibling chunks
               └─ Ollama prompt with context → answer
                   └─ _strip_apology() → clean output
```

---

## Data Flow: Full Ingestion Cycle

```
1. User triggers: POST /api/store/file (multipart upload)
                  OR POST /api/store/url
                  OR file written to watch_data/ (watchdog)

2. router.py: Extract text
   └── document_parser / web_scraper / ocr_pipeline / image_captioning

3. router.py: _process_and_store(text, source_type, source)
   ├── summarizer.summarize(text)           → summary
   ├── tagger.generate_tags(text)           → tags[]
   ├── chunker.chunk_text(text)             → chunks[]
   ├── embedder.embed_texts(chunks)         → embeddings[]
   └── vector_store.add_chunks(...)         → stored in ChromaDB

4. Response: IngestResponse{ id, summary, source_type, tags, chunk_count }
```

---

## Data Flow: Full Query Cycle

```
1. User sends: POST /api/chat { query: "...", top_k: 5 }

2. rag_pipeline.answer_query(query, top_k):
   a. Classify query
   b. Embed query (BGE)
   c. Hybrid search → top candidates
   d. Dedup by source
   e. Cross-encoder rerank
   f. Evaluate retrieval quality
   g. CRAG if poor quality
   h. Build context (+ sibling chunks)
   i. Ollama generation
   j. Strip apologies
   k. (optional) RAGAS evaluation

3. Response: ChatResponse{
     answer: str,
     sources: StoredItem[],
     crag_triggered: bool,
     evaluation: EvaluationScores | null
   }
```

---

## Async Architecture

The backend uses **FastAPI's async capability** with one background task:

```
main.py lifespan startup:
  ├── asyncio.create_task(watchdog_consumer())
  └── Thread pool executor for blocking ML operations

watchdog_consumer():
  while True:
    path = await file_queue.get()
    loop.run_in_executor(executor, _process_file_sync, path)
    file_queue.task_done()
```

ML model calls (embed, rerank, summarize) are all CPU/GPU-bound and **synchronous** — they run in a thread pool via `run_in_executor` to avoid blocking the event loop.

HTTP endpoint handlers are `async def` but call synchronous processing via `await asyncio.get_event_loop().run_in_executor(None, sync_fn)`.

---

## Module Dependency Graph

```
main.py
  └── ingestion/router.py
        ├── extraction/document_parser.py
        ├── extraction/image_captioning.py
        ├── extraction/ocr_pipeline.py
        ├── extraction/web_scraper.py
        ├── processing/summarizer.py
        ├── processing/tagger.py
        ├── processing/chunker.py
        ├── processing/embedder.py
        ├── retrieval/rag_pipeline.py
        │     ├── processing/embedder.py
        │     ├── processing/reranker.py
        │     ├── storage/vector_store.py
        │     └── retrieval/evaluator.py
        ├── storage/vector_store.py
        ├── ingestion/bookmark_sync.py
        └── ingestion/watchdog_agent.py

All modules:
  └── app/config.py  (settings singleton)
  └── app/utils/logger.py  (per-module logger)
```

---

## Design Decisions

### Why FastAPI?
- Native async support for non-blocking I/O
- Automatic OpenAPI documentation
- Pydantic v2 for fast validation
- Easy background task integration

### Why ChromaDB?
- Embedded (no separate service needed)
- Supports cosine similarity natively
- Where-document keyword filtering for hybrid search
- Python-first API, simple metadata filtering

### Why Ollama + local model?
- Privacy: no data leaves the machine
- No API costs or rate limits
- Granite 3.1 Dense 2B runs on consumer GPU/CPU

### Why hybrid search over pure vector search?
- Vector search captures semantic similarity but can miss exact keyword matches
- Keyword search finds exact terms but misses paraphrases
- RRF fusion gives the best of both without hyperparameter tuning

### Why cross-encoder reranking?
- Initial retrieval (BGE bi-encoder) is fast but approximate
- Cross-encoder (ms-marco) jointly encodes query+document → much more accurate relevance scores
- The two-stage approach trades speed for precision
