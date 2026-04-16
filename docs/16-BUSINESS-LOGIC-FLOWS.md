# 16 — Business Logic Flows

This document walks through every major user interaction as a step-by-step technical flow, connecting user actions to the code that handles them.

---

## Flow 1: User Sends a Chat Message

**User action:** Types "How does DRS work in Formula 1?" and presses Enter.

```
FRONTEND
─────────────────────────────────────────────────────
1. ChatInput.tsx: textarea keydown → Enter (no Shift)
   → calls handleSend(text) in Index.tsx

2. Index.tsx: handleSend()
   a. Creates userMsg = { role: "user", content: "How does DRS work...", timestamp: new Date() }
   b. setMessages([...prev, userMsg])
   c. setIsLoading(true)
   d. calls api.chat({ query: text, top_k: 5, evaluate: false })

3. api.ts: apiFetch("/api/chat", { method: "POST", body: JSON.stringify(req) })
   → HTTP POST to http://localhost:8000/api/chat

BACKEND
─────────────────────────────────────────────────────
4. router.py: POST /chat
   → calls answer_query(query="How does DRS work in Formula 1?", top_k=5)

5. rag_pipeline.answer_query():
   a. _is_conversational("how does drs work in formula 1?") → False
   b. _is_weather_query(...) → False
   c. kb_query = _is_kb_query(...) → False (no "bookmark", "my document" etc.)
   d. embedder.embed_text(query) → float[768]
   e. vector_store.hybrid_search(query, embedding, top_k=15) → candidates[]
   f. _deduplicate_by_source(candidates, max_per_source=2) → deduped[]
   g. reranker.rerank(query, deduped, top_k=5) → results[]
   h. max_rerank = max(r["rerank_score"] for r in results) → e.g., 4.2
   i. _is_domain_query("how does drs work in formula 1?") → True ("drs", "formula")
   j. Since domain query AND max_rerank >= 2.5: proceed to answer
   
   k. quality = _evaluate_retrieval_quality(results) → "good" (3+ results score > 2.0)
   l. crag_triggered = False (quality is good)
   
   m. context = build_context(results):
      - For each result: get_sibling_chunks(doc_id, window=1)
      - Assemble context string with chunk_text + siblings
   
   n. Ollama call:
      prompt = "Context:\n{context}\n\nQuestion: How does DRS work?\nAnswer:"
      answer = _query_ollama(prompt, context)
      → "DRS (Drag Reduction System) is a movable rear wing element..."
   
   o. _strip_apology(answer) → removes any trailing boilerplate
   
   p. Return: {
        "answer": "DRS (Drag Reduction System)...",
        "sources": [top 5 results],
        "crag_triggered": False,
        "evaluation": None
      }

6. router.py: Return ChatResponse JSON

FRONTEND
─────────────────────────────────────────────────────
7. Index.tsx: handleSend() receives response
   a. Creates assistantMsg = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        cragTriggered: response.crag_triggered,
        evaluation: null,
        timestamp: new Date()
      }
   b. setMessages([...prev, assistantMsg])
   c. setIsLoading(false)
   d. scrollRef.current.scrollIntoView({ behavior: "smooth" })

8. ChatMessage.tsx renders assistantMsg:
   - Bot avatar (gradient circle with Bot icon)
   - Glass bubble with ReactMarkdown rendering
   - "3 sources" button (collapsed)
   - No CRAG badge (cragTriggered=false)
   - No quality badge (evaluation=null)
```

---

## Flow 2: Query Triggers CRAG (Poor Retrieval Quality)

**User action:** Types an unusual query like "What is the exact tire compound mixture specification for Pirelli C5?"

```
5. rag_pipeline.answer_query():
   ...
   g. reranker.rerank → results[]
   h. max_rerank = 0.8 (low — no good matches found)
   i. _is_domain_query("...pirelli c5...") → True ("tire" might be in keywords)
   j. Proceeds to quality check (domain query, don't fall back to web)
   
   k. _evaluate_retrieval_quality(results):
      - high_quality = count(score >= 2.0) → 0
      - → "poor"
   
   l. CRAG triggered:
      new_query = _rewrite_query(original_query)
      → "Pirelli C5 compound tire specification Formula 1"
      new_embedding = embedder.embed_text(new_query)
      new_results = hybrid_search(new_query, new_embedding, top_k * 3)
      results = reranker.rerank(new_query, new_results, top_k)
      crag_triggered = True
   
   m. Build context from improved results
   n. Ollama generation → answer
   o. Return with crag_triggered=True, query_rewritten="Pirelli C5 compound..."

FRONTEND
─────────────────────────────────────────────────────
8. assistantMsg.cragTriggered = true

9. ChatMessage.tsx renders:
   - Answer text
   - CRAG badge: amber "↺ CRAG rewrite" (RefreshCw icon)
```

---

## Flow 3: Weather Query

**User action:** Asks "What's the weather in Boston today?"

```
5. rag_pipeline.answer_query():
   a. _is_conversational → False
   b. _is_weather_query("what's the weather in boston today?") → True (regex matches "weather")
   
   c. _extract_location("what's the weather in boston today?")
      → removes: weather, in, today, what, is, the
      → returns "boston"
   
   d. _fetch_weather("boston")
      → GET https://wttr.in/boston?format=%25l%3A+%25C%2C+%25t+(feels+like+%25f)%2C+humidity+%25h%2C+wind+%25w
      → "Boston: Partly cloudy, +12°C (feels like +9°C), humidity 65%, wind 15km/h N"
   
   e. _answer_without_context(query, web_context="Boston: Partly cloudy..."):
      prompt = "Answer this question using the information below:\nInfo: Boston: Partly cloudy...\nQuestion: What's the weather in boston today?\nAnswer:"
      answer = _query_ollama(prompt) → natural language weather description
      answer = _strip_apology(answer)
   
   f. Return { "answer": "It's currently partly cloudy in Boston...", "sources": [], "crag_triggered": False }
```

---

## Flow 4: Conversational Message

**User action:** Types "Hi there! How are you?"

```
5. rag_pipeline.answer_query():
   a. _is_conversational("hi there! how are you?") → True (matches "hi" + "how are you")
   
   b. Direct Ollama call (no KB lookup):
      answer = _query_ollama("hi there! how are you?")
      → "Hi! I'm doing great, thanks for asking. I'm InfoStore, your AI knowledge base assistant..."
   
   c. Return { "answer": "Hi! I'm...", "sources": [], "crag_triggered": False }
```

---

## Flow 5: KB-Specific Query (Explicit Reference)

**User action:** Asks "Read my bookmark 'CS 5800 (algorithms)'"

```
5. rag_pipeline.answer_query():
   a. _is_conversational → False
   b. _is_weather_query → False
   c. kb_query = _is_kb_query("read my bookmark 'CS 5800 (algorithms)'") → True ("bookmark")
   
   d. embedder.embed_text(query) → float[768]
   e. hybrid_search → candidates
   f. reranker → results
   g. max_rerank = 3.8 (good — found the bookmarked page)
   
   h. kb_query=True AND max_rerank >= 2.5: proceed to answer
   
   i. build_context(results) → context from CS 5800 bookmark content
   j. Ollama → summarizes/explains CS 5800 content
   k. Return with sources showing the CS 5800 bookmark
```

**If the bookmark was never synced (max_rerank < 2.5 AND kb_query=True):**
```
   → Return {
       "answer": "I searched your knowledge base but couldn't find anything about 'CS 5800'. 
                  Try syncing your bookmarks or uploading the relevant files.",
       "sources": [],
       "crag_triggered": False
     }
```

---

## Flow 6: File Ingestion via Upload

**User action:** Clicks "Upload File" in sidebar, selects `lecture_notes.pdf`.

```
FRONTEND
─────────────────────────────────────────────────────
1. AppSidebar.tsx: fileInputRef.current.click()

2. User selects file → onChange fires:
   const formData = new FormData()
   formData.append("file", selectedFile)
   api.storeFile(formData)
   → POST /api/store/file (multipart/form-data)

BACKEND
─────────────────────────────────────────────────────
3. router.py: POST /store/file
   a. Save uploaded file to backend/uploads/lecture_notes.pdf
   b. Detect extension: .pdf → document
   c. document_parser.parse_document("uploads/lecture_notes.pdf")
      → PyPDF2 reads all pages → raw_text (e.g., 15,000 words)

4. _process_and_store(raw_text, "document", "/uploads/lecture_notes.pdf", tags=[]):
   a. summarizer.summarize(raw_text)
      → smart_truncate(raw_text, max_chars=2000) → truncated
      → T5: "summarize: {truncated}" → "Lecture notes covering sorting algorithms..."
   
   b. tagger.generate_tags(raw_text)
      → T5: "Generate 5 short topic tags..." → "sorting algorithms, big-O, merge sort, quicksort, data structures"
      → ["sorting algorithms", "big-o", "merge sort", "quicksort", "data structures"]
   
   c. chunker.chunk_text(raw_text, chunk_size=300, overlap=80)
      → _split_into_sentences(raw_text) → sentences[]
      → sliding window → 48 chunks
   
   d. (ENABLE_CONTEXTUAL_RETRIEVAL=False → skip contextualization)
   
   e. embedder.embed_texts(48 chunks, batch_size=32)
      → BGE encodes all chunks → 48 × float[768]
   
   f. vector_store.add_chunks(
        chunks=48 chunks,
        embeddings=48 embeddings,
        source_type="document",
        source="/uploads/lecture_notes.pdf",
        tags=["sorting algorithms", ...],
        summary="Lecture notes covering sorting algorithms..."
      )
      → Generates parent_id = UUID
      → Stores 48 entries in ChromaDB with shared parent_id and sequential chunk_index
   
   g. Return (chunk_ids=48 UUIDs, summary=..., tags=..., chunk_count=48)

5. router.py → Return IngestResponse:
   {
     "id": ["uuid0", ..., "uuid47"],
     "summary": "Lecture notes covering sorting algorithms...",
     "source_type": "document",
     "tags": ["sorting algorithms", "big-o", "merge sort", "quicksort", "data structures"],
     "chunk_count": 48,
     "message": "success"
   }

FRONTEND
─────────────────────────────────────────────────────
6. AppSidebar.tsx shows success toast
7. StatsBar polls /api/stats → updates document count (48 more chunks)
```

---

## Flow 7: Automatic File Indexing via Watchdog

**User action:** Drops `ferrari_technical.pdf` into `watch_data/documents/` folder.

```
OS FILE SYSTEM
─────────────────────────────────────────────────────
1. OS generates file-created event for ferrari_technical.pdf

WATCHDOG (watchdog_agent.py - in watchdog thread)
─────────────────────────────────────────────────────
2. InfoStoreHandler.on_created() fires
   → path = "E:/watch_data/documents/ferrari_technical.pdf"
   → is_document_file(path) → True (.pdf)
   → asyncio.run_coroutine_threadsafe(file_queue.put(path), event_loop)

ASYNC QUEUE
─────────────────────────────────────────────────────
3. file_queue now has: ["E:/watch_data/documents/ferrari_technical.pdf"]

WATCHDOG CONSUMER (main.py - in event loop)
─────────────────────────────────────────────────────
4. watchdog_consumer():
   path = await file_queue.get()  → "E:/watch_data/documents/ferrari_technical.pdf"
   await loop.run_in_executor(executor, _process_file_sync, path)

THREAD POOL
─────────────────────────────────────────────────────
5. _process_file_sync(path):
   a. is_source_indexed(path) → False (new file)
   b. is_document_file → True
   c. document_parser.parse_document(path) → raw_text
   d. _process_and_store(raw_text, "document", path, [])
      [Same pipeline as Flow 6: summarize → tag → chunk → embed → store]

6. Log: "Successfully indexed: ferrari_technical.pdf (52 chunks)"
```

---

## Flow 8: Bookmark Sync

**User action:** Clicks "Sync Bookmarks" in the sidebar.

```
FRONTEND
─────────────────────────────────────────────────────
1. AppSidebar.tsx: 
   api.syncBookmarks({ bookmark_path: null, max_bookmarks: 500 })
   → POST /api/bookmarks/sync

BACKEND
─────────────────────────────────────────────────────
2. router.py: POST /bookmarks/sync
   → background_tasks.add_task(_sync_bookmarks_task, settings.bookmark_path, 500)
   → Return immediately: { "message": "Bookmark sync started", "status": "running" }

3. _sync_bookmarks_task() runs in background:
   a. bookmark_sync.parse_chrome_bookmarks(path)
      → reads Chrome Bookmarks JSON
      → recursively extracts all urls
      → returns 312 bookmarks
   
   b. For each bookmark (url, title, folder):
      - is_source_indexed(url) → True (267 already indexed) → skipped++
      - is_source_indexed(url) → False (45 new) → process:
        a. web_scraper.extract_from_url(url)
           → trafilatura scrapes page text (or playwright for JS-heavy)
        b. _process_and_store(text, "bookmark", url, tags=[])
           [Full pipeline: summarize → tag → chunk → embed → store]
        c. synced++
   
   c. Log: "Bookmark sync complete: 45 synced, 267 skipped, 3 failed"

FRONTEND
─────────────────────────────────────────────────────
4. StatsBar polls every 5s during sync:
   GET /api/stats → sees bookmark count increasing
   Updates animated counters in real-time
```

---

## Flow 9: Semantic Search (Not Chat)

**User action:** (Alternative UI mode) Searches "aerodynamic downforce."

```
FRONTEND (if search mode is implemented)
─────────────────────────────────────────────────────
1. api.search({ query: "aerodynamic downforce", top_k: 5 })
   → POST /api/search

BACKEND
─────────────────────────────────────────────────────
2. router.py: POST /search
   a. embedder.embed_text("aerodynamic downforce") → float[768]
   b. vector_store.hybrid_search(query, embedding, top_k=5)
      → dense search: 15 candidates
      → keyword search (where_document contains "aerodynamic" or "downforce")
      → RRF fusion → merged top 15
   c. reranker.rerank(query, candidates, top_k=5) → 5 results
   d. Return SearchResponse { results: [...], query: "...", total: 5 }
```

---

## Flow 10: Force Re-index

**User action:** Calls `POST /api/watchdog/force-reindex` (or triggers via API).

```
BACKEND
─────────────────────────────────────────────────────
1. router.py: POST /watchdog/force-reindex
   
   For each dir in watch_dirs:
     For each file in dir (rglob):
       a. vector_store.delete_by_source(file_path)
          → ChromaDB: get all chunks where source==file_path
          → collection.delete(ids=[...])
          → returns count deleted
          deleted_total += count
       
       b. file_queue.put_nowait(file_path)
          → queued for re-processing by watchdog_consumer
          queued_total += 1
   
   Return { "deleted_chunks": 968, "queued": 31, "message": "..." }

2. watchdog_consumer processes queue:
   → All 31 files re-indexed with new chunker settings
```

---

## Flow 11: RAGAS Evaluation

**User action:** Same chat query but with `evaluate: true`.

```
5. rag_pipeline.answer_query(query, top_k=5, evaluate=True):
   ... [normal flow through step n] ...
   
   o. evaluate=True:
      evaluator.evaluate_rag(
        query="How does DRS work?",
        answer="DRS (Drag Reduction System) is...",
        retrieved_chunks=[r["chunk_text"] for r in results]
      )
      
      → evaluate_faithfulness(answer, chunks):
         Split answer into sentences (3 sentences)
         For each sentence: check if key tokens appear in any chunk
         grounded = 3/3 → 1.0
      
      → evaluate_relevancy(query, answer):
         q_terms = {"how", "does", "drs", "work"}
         a_terms = set(answer.lower().split())
         overlap = {"drs"} → 1/4 = 0.25 (low, query words are short)
      
      → evaluate_context_precision(query, chunks):
         For each chunk: count query term overlaps
         relevant = 4/5 chunks → 0.8
      
      → overall = mean([1.0, 0.25, 0.8]) = 0.68
      
      → Returns EvaluationScores {
          faithfulness: 1.0,
          answer_relevancy: 0.25,
          context_precision: 0.8,
          overall: 0.68
        }

FRONTEND
─────────────────────────────────────────────────────
6. message.evaluation = { faithfulness: 1.0, ... }

7. ChatMessage.tsx shows quality badge:
   "Quality: 68% (F:100 R:25 P:80)"
```

---

## Summary: Query Routing Decision Tree

```
query
  │
  ├─[is conversational?]──Yes──► Ollama direct (no KB)
  │
  ├─[is weather query?]──Yes──► wttr.in → Ollama format
  │
  └─[else]
       │
       ├─[kb_query = has explicit KB reference?]
       ├─[embed query]
       ├─[hybrid search + dedup + rerank]
       ├─[max_rerank_score]
       │
       ├─[score < 2.5 AND NOT domain AND NOT kb]──► DuckDuckGo / Ollama only
       │
       ├─[score < 2.5 AND kb]──► "Not found in KB" message
       │
       └─[score >= 2.5 OR domain]
            │
            ├─[evaluate quality → "poor"?]──Yes──► CRAG rewrite + re-retrieve
            │
            ├─[build context (+ sibling chunks)]
            ├─[Ollama generation]
            ├─[strip apology]
            └─[optional RAGAS evaluation]
                    │
                    └──► Return answer + sources + badges
```
