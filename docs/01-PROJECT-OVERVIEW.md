# 01 — Project Overview

## What Is InfoStore?

InfoStore v2 is a **multimodal AI-powered personal knowledge base**. It lets you ingest content from virtually any source — web pages, PDFs, images, notes, Chrome bookmarks, and file system directories — and then ask natural language questions that get answered by retrieving the most relevant stored content and generating a response using a local LLM.

The system is entirely **local-first**: all models run on your machine (via Ollama and HuggingFace), no content is sent to external AI APIs.

---

## Goals

| Goal | Implementation |
|------|----------------|
| Ingest any content type | PDF, DOCX, TXT, images, URLs, bookmarks, notes |
| High-quality retrieval | Hybrid search (vector + keyword) + cross-encoder reranking + CRAG |
| Private & local | Ollama local LLM, HuggingFace models, ChromaDB local vector DB |
| Multimodal | OCR + BLIP image captioning enables querying image content |
| Real-time awareness | wttr.in weather, DuckDuckGo Instant Answers for non-KB queries |
| Seamless background ingestion | File system watchdog auto-indexes new files |
| Developer-friendly | FastAPI backend, React frontend, all config via `.env` |

---

## Key Features

### Ingestion
- **URLs** — Smart web scraping: Trafilatura (fast) with Playwright fallback for JS-heavy SPAs
- **Documents** — PDF (PyPDF2), DOCX (python-docx), TXT/MD direct read
- **Images** — EasyOCR for text extraction, fine-tuned BLIP for visual captions
- **Bookmarks** — Chrome Bookmarks JSON parser with URL deduplication
- **File Watchdog** — Monitors configurable directories; auto-indexes new files, skips already-indexed ones
- **Text Notes** — Direct text input with optional title

### Processing
- **Summarization** — Fine-tuned T5 (seq2seq, CNN/DailyMail) generates display-friendly summaries
- **Auto-tagging** — T5 generates topic tags (e.g., "machine learning, neural networks, backpropagation")
- **Sentence-aware chunking** — Splits text at sentence boundaries, 300-word chunks with 80-word overlap
- **Contextual retrieval** — Optional per-chunk LLM prefix (Anthropic technique) for richer embeddings
- **Embeddings** — BGE-base-en-v1.5 (768-dim, L2-normalized cosine similarity)

### Retrieval
- **Hybrid search** — Dense vector search + keyword document search, fused with RRF (k=60)
- **Cross-encoder reranking** — ms-marco-MiniLM-L-6-v2 scores query-document pairs precisely
- **Parent-child context expansion** — Retrieves sibling chunks for richer LLM context
- **CRAG** — Corrective RAG: poor-quality retrievals trigger query rewriting and re-retrieval
- **Query routing** — Detects conversational, KB-specific, domain-specific, and weather queries

### Answer Generation
- **Ollama LLM** — IBM Granite 3.1 Dense (2B params) for fast local inference
- **T5 fallback** — Used when Ollama is unavailable
- **Web search fallback** — Weather queries hit wttr.in, general queries use DuckDuckGo Instant Answers
- **Apology stripping** — Post-processing removes LLM boilerplate phrases

### Evaluation (optional)
- **RAGAS-style metrics** — faithfulness, answer_relevancy, context_precision, overall score
- **Per-response badge** — Frontend displays quality scores on each answer

---

## Technology Stack

### Backend
| Layer | Technology | Version |
|-------|------------|---------|
| Web framework | FastAPI | 0.110+ |
| ASGI server | Uvicorn | latest |
| Vector database | ChromaDB | latest |
| LLM inference | Ollama (Granite 3.1 Dense 2B) | local |
| Summarizer | T5 fine-tuned (transformers) | HuggingFace |
| Embeddings | BAAI/bge-base-en-v1.5 (sentence-transformers) | MTEB leader |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | sentence-transformers |
| Image captioning | Salesforce/BLIP + LoRA adapter | PEFT |
| OCR | EasyOCR + pytesseract | - |
| Web scraping | trafilatura + Playwright | async |
| File watching | watchdog | Python library |
| Config | Pydantic Settings | v2 |

### Frontend
| Layer | Technology |
|-------|------------|
| Framework | React 18 |
| Build tool | Vite + SWC |
| Styling | Tailwind CSS v3 + CSS variables |
| Component library | shadcn/ui (Radix UI primitives) |
| Animation | Framer Motion |
| Markdown rendering | react-markdown |
| State management | React hooks (useState, useRef, useEffect) |
| HTTP client | Native fetch with timeout wrapper |
| Theming | next-themes (dark/light) |
| Router | react-router-dom v6 |
| Testing | Playwright (E2E) + Vitest (unit) |

---

## Course Context

This project was built for **CS5130 — Advanced Programming Principles** at Northeastern University as a semester-long capstone project. The technical goals included:

1. Building a full-stack AI application from scratch
2. Fine-tuning ML models (T5 summarizer, BLIP captioner) and integrating them into a production pipeline
3. Implementing advanced RAG techniques: hybrid search, RRF, CRAG, cross-encoder reranking, contextual retrieval
4. Designing a system with real-time background processing (watchdog, async queue)
5. Delivering a polished, usable UI with glassmorphism design

---

## Project Boundaries (What It Does NOT Do)

- No user authentication — single-user local application
- No cloud storage — all data stays on machine
- No fine-tuned retrieval model — uses off-the-shelf BGE/cross-encoder
- No streaming LLM responses — full answer returned as one HTTP response
- No collaborative features — single user knowledge base
- No persistent chat history — conversation context not stored between sessions
