# InfoStore v2 — Challenges Faced & Solutions

## 1. Fine-Tuned T5 Model Integration

**Challenge:** The project had a fine-tuned T5-base model (trained on XSum/CNN-DailyMail on an H200 GPU) stored at `backend/app/models/t5_finetuned/final_model_h200/`, but the config still pointed to the base HuggingFace model `google/flan-t5-base`. The `.env` file also overrode the config with the base model name.

**Solution:** Updated both `config.py` and `.env` to point to the local fine-tuned model path. Had to use absolute paths because relative paths caused HuggingFace's `from_pretrained()` to interpret them as repo IDs, throwing "Repo id must be in the form 'repo_name' or 'namespace/repo_name'" errors.

---

## 2. Apple Silicon (MPS) Device Compatibility

**Challenge:** The BGE embedding model (`BAAI/bge-base-en-v1.5`) hung indefinitely when loaded on Apple's MPS (Metal Performance Shaders) device. The server became completely unresponsive — no API requests could be served.

**Solution:** Added MPS-to-CPU fallback in the embedder (`device = DEVICE if DEVICE != "mps" else "cpu"`), matching the pattern already used by the summarizer and tagger. This resolved the hang while maintaining GPU acceleration on CUDA systems.

---

## 3. Async Event Loop Blocking

**Challenge:** All ML-heavy operations (summarization, embedding, tagging, OCR, image captioning) ran synchronously on the FastAPI async event loop. When the watchdog tried to process thousands of files, or when a user made a chat/search request, the entire server froze — health checks timed out, stats returned nothing, and the frontend showed "Offline."

**Solution:**
- Moved all CPU-intensive ML calls to thread pools using `asyncio.run_in_executor()` for API endpoints.
- Created a dedicated `ThreadPoolExecutor(max_workers=1)` for the watchdog consumer, ensuring file processing never blocks the API.
- This allowed the server to remain responsive while processing files in the background.

---

## 4. Watchdog Auto-Start

**Challenge:** The file system watchdog required a manual API call (`POST /api/watchdog/start`) every time the server started. This meant users had to remember to activate it after each restart.

**Solution:** Added auto-start logic in the FastAPI lifespan handler that reads `WATCH_DIRS` from the `.env` config and automatically starts the watchdog on server boot. Directories are validated (must exist) before scheduling.

---

## 5. Bookmark Sync Timeout

**Challenge:** Chrome had 216 bookmarks. The bookmark sync endpoint processed them sequentially in a single HTTP request — scraping each URL, summarizing, embedding, and storing. This took so long that HTTP clients (curl, browser) timed out, killing the connection. Only 21 of 216 bookmarks got processed before the first timeout.

**Solution:**
- Converted bookmark sync to a background async task that returns immediately.
- Added deduplication — already-synced bookmarks are skipped on subsequent calls.
- Implemented concurrent processing with `asyncio.Semaphore(5)` — 5 bookmarks scraped in parallel.
- Added a `/api/bookmarks/status` endpoint to check progress.
- Frontend polls status every 5 seconds during sync, showing a live "Syncing X/Y" indicator.

---

## 6. Web Scraping Failures (Cloudflare, Slow Sites)

**Challenge:** Many bookmarked URLs were protected by Cloudflare bot detection, returning "Performing security verification" instead of actual content. Playwright (used as fallback for JS-heavy sites) used `wait_until="networkidle"` with a 30-second timeout, making each failed scrape extremely slow.

**Solution:**
- Reduced Playwright timeout to 15 seconds with `wait_until="domcontentloaded"`.
- Added Cloudflare detection — if "security verification" is detected, waits 5 seconds for the challenge to resolve.
- Set a realistic user-agent string to reduce bot detection.
- Added a skip list for URLs that will never have useful content (Outlook, Gmail, auth pages).
- Filtered Cloudflare-only pages from being stored as valid content.

---

## 7. RAG Answer Quality — T5 Hallucination

**Challenge:** The original RAG pipeline used `google/flan-t5-large` for answer generation. This model was too small for conversational Q&A and produced:
- Hallucinated answers ("eso-community.net is about Esperanto" — completely wrong)
- Garbage output (strings of random numbers)
- Wrong topic answers ("E-Sports" when asked about ResumeCraft)
- Repetitive filler text ("The relevant information to answer the above question is:")

**Solution:** Replaced flan-t5-large with **IBM Granite 3.1 Dense 8B** running locally via Ollama. This model:
- Generates grounded, conversational answers
- Is honest about limitations ("there isn't specific mention of...")
- Never hallucinates — only uses provided context
- Produces well-structured, readable responses
- The fine-tuned T5-base was kept for summarization/tagging (its trained task), while Granite handles the generative Q&A.

---

## 8. Noisy OCR Results Polluting Search

**Challenge:** LightShot screenshot images (13K+) were processed through OCR, producing garbled text summaries (random game chat, foreign languages, gibberish). These noisy entries had deceptively low vector distances (0.30-0.45), appearing in search results for almost any query and degrading answer quality.

**Solution:**
- Implemented a multi-layered quality filter for RAG results:
  - Distance threshold (0.45 cosine distance maximum)
  - Minimum summary length (30 characters)
  - Garbage content detection (Cloudflare pages, bot checks)
  - OCR noise detection (high ratio of 1-2 character words indicates garbled text)
- RAG pipeline fetches 3x more results than needed, filters to quality ones, then uses only those for answer generation.
- Sources shown to the user are also quality-filtered.

---

## 9. Frontend Redesign

**Challenge:** The original React frontend had a traditional dashboard layout that was confusing for demos. The chat kept spinning forever (async blocking issue), stats showed 0, and the UI wasn't presentation-ready.

**Solution:**
- Redesigned using Loveable AI to generate a ChatGPT-style interface with:
  - Dark glassmorphism theme with gradient accents
  - Chat/Search mode toggle
  - Collapsible sidebar with quick actions
  - Live stats bar with animated counters
- Stats bar shows both files-on-disk counts (Images, Documents, Bookmarks) and indexed count
- Auto-refresh every 5s during active sync, 30s when idle
- 120-second fetch timeout to handle slow model loading
- Live bookmark sync progress indicator with spinning animation

---

## 10. Stats Accuracy

**Challenge:** The stats endpoint only showed ChromaDB document count (items processed through the ML pipeline), which was much lower than the actual files on disk. Users expected to see their 14K+ images and 3K+ documents reflected in the UI.

**Solution:**
- Extended the stats endpoint to count actual files on disk by scanning watch directories.
- Added Chrome bookmark count by parsing the bookmarks JSON file directly.
- Frontend displays both: "Total Files 5,772 | Images 1,999 | Documents 3,557 | Bookmarks 216" alongside "Indexed 706."
- This gives an honest picture: total data available vs. what's been processed into the knowledge base.

---

## Architecture Summary

| Component | Model/Technology | Purpose |
|-----------|-----------------|---------|
| Summarization | Fine-tuned T5-base (local) | Summarize ingested content |
| Tagging | Fine-tuned T5-base (local) | Auto-generate topic tags |
| Image Captioning | Fine-tuned BLIP + LoRA (local) | Describe visual images |
| Embeddings | BGE-base-en-v1.5 (local) | Semantic search vectors |
| RAG Answer Generation | Granite 3.1 8B via Ollama (local) | Conversational Q&A |
| Vector Database | ChromaDB | Storage and retrieval |
| Web Scraping | Trafilatura + Playwright | URL content extraction |
| OCR | EasyOCR + Tesseract | Image text extraction |
| File Monitoring | Python Watchdog | Auto-detect new files |
| Frontend | React + TypeScript + Vite | ChatGPT-style interface |
| Backend | FastAPI + Uvicorn | Async API server |
