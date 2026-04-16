# 06 — Layers and Components

This document provides a detailed technical reference for every backend module and frontend component.

---

## Backend Modules

### `app/main.py` — Application Entry Point

**Responsibilities:**
- Creates and configures the FastAPI application instance
- Sets up CORS middleware (allows `http://localhost:5173`)
- Defines the `lifespan` context manager for startup/shutdown hooks
- Starts the watchdog file consumer background task
- Warms up Ollama on startup (prevents cold start on first query)

**Key functions:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    asyncio.create_task(watchdog_consumer())   # Background file processor
    warmup_ollama()                            # Pre-load Ollama model
    if settings.watch_dirs:
        start_watchdog(settings.watch_dirs.split(","))
    yield
    # SHUTDOWN
    stop_watchdog()

async def watchdog_consumer():
    """Infinite loop: pull file paths from queue, process in thread pool."""
    executor = ThreadPoolExecutor(max_workers=2)
    while True:
        path = await file_queue.get()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _process_file_sync, path)
        file_queue.task_done()
```

---

### `app/config.py` — Settings

**Pattern:** Singleton Pydantic `BaseSettings` — loads from `.env`, with defaults.

```python
settings = Settings()   # Imported everywhere as: from app.config import settings
DEVICE = _get_device()  # "cuda" | "mps" | "cpu"
```

Device detection logic:
```python
def _get_device(s: Settings) -> str:
    if s.device_preference == "cuda" and torch.cuda.is_available():
        return "cuda"
    if s.device_preference == "mps" and torch.backends.mps.is_available():
        return "mps"
    if s.device_preference == "auto":
        if torch.cuda.is_available(): return "cuda"
        if torch.backends.mps.is_available(): return "mps"
    return "cpu"
```

---

### `app/ingestion/router.py` — API Router

**All API endpoints live here.** Uses `APIRouter` mounted at `/api` in `main.py`.

**Helper functions (not endpoints):**

`_contextualize_chunk(chunk, full_text, source)`:
- Sends a prompt to Ollama: "Given this document, give brief context for this chunk"
- Returns the chunk prefixed with the context (Anthropic's contextual retrieval technique)
- Only called when `ENABLE_CONTEXTUAL_RETRIEVAL=True`

`_process_and_store(text, source_type, source, tags, title)`:
- Orchestrates the full ingestion pipeline:
  1. `summarizer.summarize(text)` → display summary
  2. `tagger.generate_tags(text)` → topic tags
  3. `chunker.chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)` → text chunks
  4. Optionally contextualize each chunk
  5. `embedder.embed_texts(chunks)` → embeddings
  6. `vector_store.add_chunks(...)` → store in ChromaDB
- Returns `(chunk_ids, summary, tags, chunk_count)`

`_process_image(file_path)`:
- Runs OCR: `ocr_pipeline.run_ocr(path)` → `(ocr_text, method)`
- If OCR text ≥ 20 chars: store as `image_ocr` with OCR text
- Otherwise: run `image_captioning.generate_caption(path)` → store as `image_caption`

---

### `app/ingestion/bookmark_sync.py` — Bookmark Parser

Parses the Chrome Bookmarks JSON file (at path from `settings.bookmark_path`).

```python
def parse_chrome_bookmarks(path: str) -> list[dict]:
    """Returns list of {url, title, date_added, folder}."""

def _extract_bookmarks(node: dict, folder: str, results: list):
    """Recursively traverses the nested bookmark tree."""
    if node.get("type") == "url":
        results.append({
            "url": node["url"],
            "title": node.get("name", ""),
            "date_added": _chrome_epoch_to_unix(node.get("date_added", 0)),
            "folder": folder
        })
    for child in node.get("children", []):
        _extract_bookmarks(child, child.get("name", folder), results)
```

Chrome stores timestamps as microseconds since Jan 1, 1601. The conversion:
```python
def _chrome_epoch_to_unix(chrome_time: int) -> int:
    CHROME_EPOCH_OFFSET = 11644473600 * 1_000_000
    return (chrome_time - CHROME_EPOCH_OFFSET) // 1_000_000
```

---

### `app/ingestion/watchdog_agent.py` — File System Watchdog

Uses the `watchdog` Python library to monitor directories for new files.

```python
class InfoStoreHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            path = event.src_path
            if is_image_file(path) or is_document_file(path):
                asyncio.run_coroutine_threadsafe(
                    file_queue.put(path), 
                    asyncio.get_event_loop()
                )

file_queue: asyncio.Queue = asyncio.Queue()  # Global async queue

def start_watchdog(dirs: list[str]):
    """Start Observer, pre-queue existing unindexed files."""
    observer = Observer()
    for d in dirs:
        observer.schedule(InfoStoreHandler(), d, recursive=True)
    observer.start()
    # Pre-queue existing files
    for d in dirs:
        for f in Path(d).rglob("*"):
            if f.is_file() and not is_source_indexed(str(f)):
                file_queue.put_nowait(str(f))
```

---

### `app/extraction/document_parser.py` — Document Text Extraction

```python
def parse_document(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":   return extract_from_pdf(file_path)
    if ext == ".docx":  return extract_from_docx(file_path)
    if ext in (".txt", ".md", ".csv", ".json"):
        return extract_from_text(file_path)
    return ""

def extract_from_pdf(path: str) -> str:
    reader = PyPDF2.PdfReader(path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)

def extract_from_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
```

---

### `app/extraction/image_captioning.py` — BLIP Captioning

**Model:** `Salesforce/blip-image-captioning-base` with optional LoRA adapter.

```python
def _load_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained(...)
    
    lora_path = settings.blip_model_path
    if Path(lora_path).exists():
        model = PeftModel.from_pretrained(model, lora_path)  # LoRA adapter
        model = model.merge_and_unload()                     # Merge for inference
    
    return processor, model.to(DEVICE)

def generate_caption(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(DEVICE)
    ids = model.generate(**inputs, max_new_tokens=100)
    return processor.decode(ids[0], skip_special_tokens=True)
```

---

### `app/extraction/ocr_pipeline.py` — OCR

Two-tier OCR with fallback:

```python
def run_ocr(image_path: str) -> tuple[str, str]:
    """Returns (extracted_text, method_used)."""
    text, method = extract_text_easyocr(image_path)
    if len(text.strip()) < 20:
        tesseract_text, _ = extract_text_tesseract(image_path)
        if len(tesseract_text) > len(text):
            return tesseract_text, "tesseract"
    return text, method
```

EasyOCR handles most cases well (GPU-accelerated, multi-language). Tesseract is a fallback for edge cases.

---

### `app/extraction/web_scraper.py` — Web Scraping

```python
def extract_from_url(url: str) -> str:
    """Skip login/mail URLs, try Trafilatura, fall back to Playwright."""
    if any(skip in url for skip in ["login", "signin", "mail", "oauth"]):
        raise ValueError(f"Skipping auth/mail URL: {url}")
    
    text = scrape_with_trafilatura(url)
    if text and len(text) >= 50:
        return text
    return asyncio.run(scrape_with_playwright(url))

async def scrape_with_playwright(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_timeout(3000)  # JS rendering
        content = await page.content()
        return trafilatura.extract(content) or ""
```

---

### `app/processing/chunker.py` — Sentence-Aware Chunking

**Core design:** Never cut mid-sentence. Respect paragraph structure.

```python
def _split_into_sentences(text: str) -> list[str]:
    # 1. Normalize: collapse 3+ blank lines to 2
    # 2. Split by "\n\n" (paragraph breaks = hard boundaries)
    # 3. Within each paragraph: split on [.!?] followed by whitespace+capital
    # 4. List items (lines starting with - • * or digits) = individual sentences

def chunk_text(text: str, chunk_size=300, overlap=80) -> list[str]:
    sentences = _split_into_sentences(text)
    # If total_words <= chunk_size: return [full_text] (one chunk)
    # Otherwise: sliding window accumulating sentences up to chunk_size words
    # Overlap: step back from end of chunk to find overlap_words worth of sentences
    # Guarantee forward progress: start_idx = max(new_start, start_idx + 1)
```

**Parameters (from `.env`):**
- `CHUNK_SIZE=300` — Target words per chunk
- `CHUNK_OVERLAP=80` — Words of overlap between consecutive chunks

---

### `app/processing/embedder.py` — Text Embeddings

```python
_model = SentenceTransformer("BAAI/bge-base-en-v1.5", device=DEVICE)

def embed_text(text: str) -> list[float]:
    return _model.encode(text, normalize_embeddings=True).tolist()

def embed_texts(texts: list[str], batch_size=32) -> list[list[float]]:
    return _model.encode(texts, batch_size=batch_size, 
                         normalize_embeddings=True).tolist()
```

BGE requires a query prefix for retrieval:
- Queries: `"Represent this sentence for searching relevant passages: {text}"`
- Documents: stored as-is

---

### `app/processing/reranker.py` — Cross-Encoder Reranking

```python
_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=DEVICE)

def rerank(query: str, documents: list[dict], top_k=5) -> list[dict]:
    pairs = [(query, doc["chunk_text"] or doc["summary"]) for doc in documents]
    scores = _model.predict(pairs)  # Joint query-document scoring
    for doc, score in zip(documents, scores):
        doc["rerank_score"] = float(score)
    return sorted(documents, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
```

---

### `app/processing/summarizer.py` — T5 Summarization

```python
_tokenizer = AutoTokenizer.from_pretrained(settings.summarizer_model)
_model = AutoModelForSeq2SeqLM.from_pretrained(settings.summarizer_model)

def summarize(text: str, max_length=150, min_length=30) -> str:
    truncated = smart_truncate(text, max_chars=2000)
    inputs = _tokenizer("summarize: " + truncated, return_tensors="pt", 
                        max_length=512, truncation=True)
    outputs = _model.generate(
        **inputs,
        max_length=max_length,
        min_length=min_length,
        num_beams=4,
        repetition_penalty=1.2,
        no_repeat_ngram_size=3,
        early_stopping=True
    )
    return _tokenizer.decode(outputs[0], skip_special_tokens=True)
```

---

### `app/processing/tagger.py` — Auto-Tagging

```python
def generate_tags(text: str, max_tags=5) -> list[str]:
    prompt = f"Generate {max_tags} short topic tags for this text, separated by commas: {text[:500]}"
    inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
    outputs = model.generate(**inputs, max_new_tokens=50)
    raw = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Split on comma/semicolon, strip, deduplicate, return first max_tags
    tags = [t.strip().lower() for t in re.split(r"[,;]", raw) if t.strip()]
    return list(dict.fromkeys(tags))[:max_tags]
```

---

### `app/storage/vector_store.py` — ChromaDB Wrapper

Key functions:

| Function | Description |
|----------|-------------|
| `add_entry(summary, embedding, ...)` | Single legacy entry |
| `add_chunks(chunks, embeddings, ...)` | Batch insert with shared parent_id |
| `search(query_embedding, top_k, where)` | Pure vector similarity search |
| `hybrid_search(query_text, query_embedding, top_k)` | Dense + keyword with RRF |
| `get_sibling_chunks(doc_id, window)` | Get neighboring chunks for context expansion |
| `get_collection_stats()` | Counts, types, file system stats |
| `is_source_indexed(source)` | Check if already in DB |
| `delete_by_source(source)` | Delete all chunks for a source |
| `delete_entry(doc_id)` | Delete doc + all siblings |

**RRF Fusion (k=60):**
```python
# For each result in each ranked list:
rrf_score[doc_id] += 1.0 / (60 + rank + 1)
# Final rank: sort by total rrf_score descending
```

---

### `app/retrieval/rag_pipeline.py` — RAG Pipeline

The most complex module. Full breakdown:

**Query Classification Functions:**
```python
_CONVERSATIONAL_PATTERNS = [
    r"^(hi|hello|hey|yo|sup|what'?s up)",
    r"^(good morning|good evening|good afternoon)",
    r"^(how are you|how('?re| are) you doing)",
    r"^(thanks?|thank you|thx|ty)",
    ...
]

def _is_conversational(query: str) -> bool:
    return any(re.match(p, query.lower().strip()) for p in _CONVERSATIONAL_PATTERNS)

def _is_kb_query(query: str) -> bool:
    """Explicit KB reference detection."""
    q = query.lower()
    return any(kw in q for kw in [
        "bookmark", "my document", "read my", "show my", "find my",
        "i saved", "i uploaded", "i added", "you indexed",
        "in my knowledge base", "from my kb", ...
    ])

def _is_domain_query(query: str) -> bool:
    """F1/motorsport domain detection."""
    DOMAIN_KEYWORDS = {"formula", "f1", "grand prix", "ferrari", "mclaren", 
                       "verstappen", "hamilton", "fia", "drs", "kers", ...}
    return any(kw in query.lower() for kw in DOMAIN_KEYWORDS)

def _is_weather_query(query: str) -> bool:
    return re.search(r"\b(weather|temperature|forecast|rain|snow|humid)\b", 
                     query, re.IGNORECASE) is not None
```

**Retrieval:**
```python
def _retrieve_and_rerank(query: str, query_embedding, top_k: int):
    candidates = vector_store.hybrid_search(query, query_embedding, top_k * 3)
    deduped = _deduplicate_by_source(candidates, max_per_source=2)
    reranked = reranker.rerank(query, deduped, top_k=top_k)
    return reranked

def _deduplicate_by_source(results, max_per_source=2):
    seen = {}
    out = []
    for r in results:
        src = r["source"]
        seen[src] = seen.get(src, 0) + 1
        if seen[src] <= max_per_source:
            out.append(r)
    return out
```

**CRAG (Corrective RAG):**
```python
def _evaluate_retrieval_quality(results, threshold_high=2.0, threshold_low=0.5) -> str:
    scores = [r.get("rerank_score", 0) for r in results]
    high = sum(1 for s in scores if s >= threshold_high)
    if high >= 3: return "good"
    if high >= 1: return "marginal"
    return "poor"

def _rewrite_query(original: str) -> str:
    """Ask Ollama to rephrase the query for better retrieval."""
    prompt = f"Rephrase this query to improve document retrieval: '{original}'"
    return _query_ollama(prompt, context="").strip()
```

**Answer Generation:**
```python
def answer_query(query: str, top_k: int = 5, evaluate: bool = False) -> dict:
    # 1. Conversational
    if _is_conversational(query):
        return {"answer": _query_ollama(query), "sources": [], ...}
    
    # 2. Weather
    if _is_weather_query(query):
        location = _extract_location(query)
        weather_data = _fetch_weather(location)
        return {"answer": _query_ollama(query, context=weather_data), ...}
    
    # 3. KB Retrieval
    kb_query = _is_kb_query(query)
    query_embedding = embedder.embed_text(query)
    results = _retrieve_and_rerank(query, query_embedding, top_k)
    
    max_rerank = max((r.get("rerank_score", 0) for r in results), default=0)
    
    if max_rerank < 2.5 and not _is_domain_query(query) and not kb_query:
        return _answer_without_context(query)
    
    if max_rerank < 2.5 and kb_query:
        return {"answer": "I searched your knowledge base but couldn't find...", ...}
    
    # 4. CRAG
    quality = _evaluate_retrieval_quality(results)
    crag_triggered = False
    if quality == "poor":
        new_query = _rewrite_query(query)
        new_embedding = embedder.embed_text(new_query)
        results = _retrieve_and_rerank(new_query, new_embedding, top_k)
        crag_triggered = True
    
    # 5. Context building + generation
    context = build_context(results)
    answer = _query_ollama(query, context=context)
    answer = _strip_apology(answer)
    
    # 6. Optional evaluation
    evaluation = None
    if evaluate:
        evaluation = evaluator.evaluate_rag(query, answer, results)
    
    return {"answer": answer, "sources": results, "crag_triggered": crag_triggered, ...}
```

**Boilerplate Stripping:**
```python
_TRAILING_BOILERPLATE = [
    r"for (?:the )?(?:most )?(?:accurate|up-to-date|current|latest|real-time)",
    r"(?:please|you (?:might|may|can|could)).*?(?:check|visit|consult)",
    r"reliable (?:weather|business|news|information|source)",
    r"official website",
    r"for (?:more|the latest|further) (?:information|details|updates?)",
    ...
]

def _strip_apology(text: str) -> str:
    # Remove leading apology patterns (regex sub)
    # Split into sentences on [.!?]
    # Pop trailing sentences that match any boilerplate pattern
    return cleaned_text
```

---

### `app/retrieval/evaluator.py` — RAGAS Metrics

Lightweight RAGAS-style evaluation without external dependencies:

```python
def evaluate_faithfulness(answer: str, context_chunks: list[str]) -> float:
    """What fraction of answer sentences are grounded in context?"""
    sentences = re.split(r"[.!?]+", answer)
    grounded = sum(1 for s in sentences if any(
        token in " ".join(context_chunks).lower() 
        for token in s.lower().split() if len(token) > 4
    ))
    return grounded / max(len(sentences), 1)

def evaluate_relevancy(query: str, answer: str) -> float:
    """Overlap between query terms and answer terms."""
    q_terms = set(query.lower().split())
    a_terms = set(answer.lower().split())
    overlap = q_terms & a_terms
    return len(overlap) / max(len(q_terms), 1)

def evaluate_context_precision(query: str, chunks: list[str]) -> float:
    """What fraction of retrieved chunks are relevant to the query?"""
    q_terms = set(query.lower().split())
    relevant = sum(1 for c in chunks if 
                   len(q_terms & set(c.lower().split())) >= 2)
    return relevant / max(len(chunks), 1)
```

---

## Frontend Components

### `src/pages/Index.tsx` — Main Chat Page

**State:**
```typescript
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [isLoading, setIsLoading] = useState(false);
const messagesEndRef = useRef<HTMLDivElement>(null);
```

**Message flow:**
```typescript
const handleSend = async (text: string) => {
  // 1. Append user message
  setMessages(prev => [...prev, userMsg]);
  setIsLoading(true);
  
  // 2. Call API
  const response = await api.chat({ query: text, top_k: 5 });
  
  // 3. Append assistant message with metadata
  setMessages(prev => [...prev, {
    role: "assistant",
    content: response.answer,
    sources: response.sources,
    cragTriggered: response.crag_triggered,
    evaluation: response.evaluation,
    ...
  }]);
  setIsLoading(false);
};
```

### `src/components/AppSidebar.tsx` — Ingestion Sidebar

Contains all ingestion UI. Modal dialogs for URL and note input. File upload via `<input type="file">`. Bookmark sync button calls `api.syncBookmarks()`. Watchdog controls with directory textarea.

### `src/components/ChatMessage.tsx` — Message Rendering

```typescript
// User messages: gradient background, right-aligned
// Assistant messages: glassmorphism, left-aligned, markdown rendered
// Sources: collapsible section with animated expand/collapse
// CRAG badge: amber, shown when cragTriggered === true
// Quality badge: emerald, shows F/R/P percentages
// Copy button: appears on hover (group/group-hover pattern), toggles Copy/Check icon
```

### `src/components/StatsBar.tsx` — Animated Stats

Polls `/api/stats` every 30s (5s when syncing). Uses `AnimatedCounter` with easing:
```typescript
function AnimatedCounter({ value }: { value: number }) {
  // useEffect → requestAnimationFrame loop
  // Easing: t => t < 0.5 ? 2*t*t : -1+(4-2*t)*t
  // Duration: 1200ms
}
```

### `src/lib/api.ts` — API Client

```typescript
const API_BASE = "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    signal: controller.signal
  });
  
  clearTimeout(timeout);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export const api = {
  health: () => apiFetch<HealthResponse>("/health"),
  stats: () => apiFetch<StatsResponse>("/api/stats"),
  chat: (req: ChatRequest) => apiFetch<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req)
  }),
  // ... etc
};
```
