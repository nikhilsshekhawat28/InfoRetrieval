# InfoStore v2 — A Multimodal AI System for Unified Content Summarization & Retrieval

**CS5130 | Northeastern University | Spring 2026**

**Team:** Vishnu Purohitham, Nimish Poonekar, Nikhil Shekhawat, Rajarshi Dey

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Project Structure](#project-structure)
4. [Setup & Installation](#setup--installation)
5. [Running the Application](#running-the-application)
6. [API Reference](#api-reference)
7. [Frontend Pages](#frontend-pages)
8. [Pipeline Details](#pipeline-details)
9. [Training Scripts (HPC)](#training-scripts-hpc)
10. [Configuration](#configuration)
11. [Docker Deployment](#docker-deployment)
12. [Tech Stack](#tech-stack)

---

## Overview

InfoStore v2 is a full-stack AI-powered knowledge base that ingests content from **URLs, images, PDFs, DOCX files, and text notes**, processes them through an AI pipeline (summarization, captioning, OCR, tagging), and stores them in a vector database for **semantic search** and **RAG-powered Q&A**.

### Problem

Personal information is fragmented — bookmarks rot in browsers, screenshots have no searchable text, notes are scattered. Traditional keyword search fails for visual data and cross-format retrieval.

### Solution

A unified system that treats all input types as first-class citizens, processes them through AI models, and enables natural language search across everything.

### What's New vs CS5100

| Feature | CS5100 | CS5130 (This Project) |
|---------|--------|----------------------|
| Ingestion | Manual URL/file only | Automated Chrome Bookmark Sync + File Watchdog |
| Web Scraping | Trafilatura (static) | Playwright (JS SPAs) + Trafilatura fallback |
| Documents | Text files only | PDF + DOCX + TXT + MD |
| OCR | EasyOCR basic | EasyOCR + Tesseract with smart routing |
| Summarization | Off-the-shelf FLAN-T5 | Fine-tuned T5 on XSum/CNN-DailyMail |
| Vector DB | SQLite-vec | ChromaDB (hybrid dense+keyword search) |
| Retrieval | Raw similarity results | RAG pipeline with LLM answer synthesis |
| Frontend | Streamlit | React + Bootstrap (dashboard, chat, tags) |
| Metadata | Basic type/source | Auto-generated tags + rich metadata |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                React / Bootstrap WebApp                      │
│          (Dashboard · Search · AI Chat · Settings)           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (Vite proxy → :8000)
┌──────────────────────────▼──────────────────────────────────┐
│                     FastAPI Backend                           │
│                                                              │
│  ┌─── LAYER 1 ───┐  ┌─── LAYER 2 ───┐  ┌─── LAYER 3 ───┐ │
│  │   INGESTION    │  │  EXTRACTION    │  │ AI PROCESSING  │ │
│  │                │  │                │  │                │ │
│  │ Bookmark Sync  │  │ Playwright     │  │ T5 Summarizer  │ │
│  │ File Watchdog  │  │ Trafilatura    │  │ BGE Embedder   │ │
│  │ Manual Upload  │  │ EasyOCR+Tess   │  │ Auto Tagger    │ │
│  │ API Endpoints  │  │ PDF/DOCX Parse │  │                │ │
│  │                │  │ BLIP Captioner │  │                │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
│                                                              │
│  ┌─── LAYER 4 ────────────────────────────────────────────┐ │
│  │              STORAGE & RETRIEVAL                        │ │
│  │                                                         │ │
│  │  ChromaDB (cosine similarity + keyword hybrid search)   │ │
│  │  RAG Pipeline: retrieve context → LLM answer synthesis  │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

```
INPUT (URL / Image / PDF / DOCX / Text / Bookmark)
  │
  ├── URL ──────────→ Trafilatura ──→ [fail?] ──→ Playwright
  │                        │                          │
  │                        └──── extracted text ───────┘
  │                                    │
  ├── Image ────────→ OCR Pipeline ────┤── text found ──→ T5 Summarize
  │                                    └── no text ─────→ BLIP Caption
  │
  ├── PDF / DOCX ───→ Document Parser ──→ extracted text ──→ T5 Summarize
  │
  ├── Text Note ─────────────────────────────────────────→ T5 Summarize
  │
  └──── All outputs ──→ Auto-Tag ──→ BGE Embed (768-dim) ──→ ChromaDB
                                                                  │
SEARCH:                                                           │
  Query ──→ BGE Embed ──→ ChromaDB Hybrid Search ──→ Top-K Results
                                    │
                          RAG Pipeline ──→ LLM Answer Synthesis
                                    │
                              React UI Display
```

---

## Project Structure

```
InfoRetrieval_v2Claude/
│
├── backend/                          # Python FastAPI backend
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point, CORS, lifespan, watchdog consumer
│   │   ├── config.py                 # Settings (env vars), device detection (CUDA/MPS/CPU)
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py            # Pydantic request/response models for all endpoints
│   │   │
│   │   ├── ingestion/                # LAYER 1: Data ingestion
│   │   │   ├── router.py             # All API endpoints (store, search, chat, bookmarks, watchdog)
│   │   │   ├── bookmark_sync.py      # Chrome Bookmarks JSON parser (recursive folder extraction)
│   │   │   └── watchdog_agent.py     # File system watcher (auto-ingest new files in directories)
│   │   │
│   │   ├── extraction/               # LAYER 2: Content extraction
│   │   │   ├── web_scraper.py        # Trafilatura (fast) + Playwright (JS-heavy) dual scraping
│   │   │   ├── ocr_pipeline.py       # EasyOCR + Tesseract with smart routing logic
│   │   │   ├── document_parser.py    # PDF (PyPDF2), DOCX (python-docx), TXT, MD, CSV, JSON
│   │   │   └── image_captioning.py   # BLIP + LoRA fine-tuned model for image descriptions
│   │   │
│   │   ├── processing/               # LAYER 3: AI processing
│   │   │   ├── summarizer.py         # T5 text summarization with smart truncation
│   │   │   ├── embedder.py           # BGE-base-en-v1.5 sentence embeddings (768-dim)
│   │   │   └── tagger.py             # Auto-tag generation using T5
│   │   │
│   │   ├── storage/
│   │   │   └── vector_store.py       # ChromaDB: add, search, hybrid search, delete, stats
│   │   │
│   │   ├── retrieval/
│   │   │   └── rag_pipeline.py       # RAG: embed query → retrieve → build context → LLM answer
│   │   │
│   │   └── utils/
│   │       └── logger.py             # Rotating file logger (5MB, 3 backups) + console output
│   │
│   ├── requirements.txt              # Python dependencies
│   ├── .env                          # Environment configuration
│   ├── .env.example                  # Template for environment variables
│   └── Dockerfile                    # Container build for backend
│
├── frontend/                         # React + Vite + Bootstrap frontend
│   ├── index.html                    # HTML entry point (loads Bootstrap CDN)
│   ├── package.json                  # Node dependencies
│   ├── vite.config.js                # Vite config with API proxy to :8000
│   └── src/
│       ├── main.jsx                  # React entry point with BrowserRouter
│       ├── App.jsx                   # Root component: navbar + route definitions
│       ├── index.css                 # Global dark theme styles
│       │
│       ├── components/
│       │   ├── SearchBar.jsx         # Reusable search input with loading state
│       │   ├── ResultCard.jsx        # Search result display (summary, tags, source badge, score)
│       │   ├── UploadPanel.jsx       # Tabbed upload: URL / Text / File with API calls
│       │   ├── ChatInterface.jsx     # RAG-powered chat with message bubbles + source cards
│       │   └── Dashboard.jsx         # Stats display (total documents, refresh button)
│       │
│       ├── pages/
│       │   ├── Home.jsx              # Dashboard + Upload panel + AI Chat (main page)
│       │   ├── Search.jsx            # Full-page semantic search with results list
│       │   └── Settings.jsx          # Watchdog config + Chrome bookmark sync/preview
│       │
│       └── services/
│           └── api.js                # Axios API client for all backend endpoints
│
├── training/                         # Fine-tuning scripts (run on HPC cluster)
│   ├── train_t5_xsum.py             # Fine-tune T5-base on XSum or CNN-DailyMail
│   ├── train_blip_flickr8k.py       # Fine-tune BLIP with LoRA on Flickr8k
│   └── evaluate.py                  # Evaluate models (ROUGE for T5, BLEU/ROUGE for BLIP)
│
├── models/
│   └── blip_finetuned/              # Fine-tuned BLIP LoRA weights (from CS5100)
│       ├── adapter_config.json       # LoRA config (r=16, alpha=32, target=query,value)
│       └── adapter_model.safetensors # Trained LoRA adapter weights
│
├── docker-compose.yml                # Multi-container orchestration (backend + frontend)
└── README.md                         # This file
```

---

## Setup & Installation

### Prerequisites

Install these **before** cloning:

| Dependency | macOS | Ubuntu/Debian |
|---|---|---|
| **Python 3.11+** | `brew install python@3.13` | `sudo apt install python3.11 python3.11-venv` |
| **Node.js 18+** | `brew install node` | `curl -fsSL https://deb.nodesource.com/setup_18.x \| sudo -E bash - && sudo apt install -y nodejs` |
| **Tesseract OCR** | `brew install tesseract` | `sudo apt install tesseract-ocr` |
| **Git LFS** | `brew install git-lfs && git lfs install` | `sudo apt install git-lfs && git lfs install` |
| **Ollama** | `brew install ollama` or [ollama.com](https://ollama.com) | `curl -fsSL https://ollama.com/install.sh \| sh` |

### Step 1: Install Ollama & Granite Model

Ollama runs the local LLM (IBM Granite 8B) that powers the RAG chat Q&A. **This is required.**

```bash
# After installing Ollama, pull the model (~5GB download)
ollama pull granite3.1-dense:8b

# Verify
ollama list
# Should show: granite3.1-dense:8b    5.0 GB

# Ollama must be running when the backend is active (serves on localhost:11434)
# On macOS it runs as a service automatically after install
# On Linux: ollama serve
```

### Step 2: Clone the Repository

```bash
git clone https://github.com/TheJASSZ/InfoRetrieval_v2.git
cd InfoRetrieval_v2
```

Git LFS will automatically download the fine-tuned model weights (~860MB T5 + 4.5MB BLIP).

### Step 3: Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (for JS-heavy web scraping)
playwright install chromium

# Copy and configure environment
cp .env.example .env
```

### Step 4: Configure Environment

Edit `backend/.env` — **update paths to match your system**:

```env
DEVICE_PREFERENCE=auto
CHROMA_PERSIST_DIR=./chroma_data
CHROMA_COLLECTION=info_store

# Models — SUMMARIZER_MODEL MUST be an absolute path
BLIP_MODEL_PATH=../models/blip_finetuned
SUMMARIZER_MODEL=/absolute/path/to/InfoRetrieval_v2/backend/app/models/t5_finetuned/final_model_h200
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
RAG_LLM_MODEL=google/flan-t5-large

# Watchdog — directories to auto-monitor (comma-separated, absolute paths)
WATCH_DIRS=/absolute/path/to/InfoRetrieval_v2/watch_data/documents,/absolute/path/to/InfoRetrieval_v2/watch_data/images
BOOKMARK_PATH=~/Library/Application Support/Google/Chrome/Default/Bookmarks

HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

> **Important:** The `SUMMARIZER_MODEL` path **must be absolute** (starting with `/`). Relative paths like `./models/...` will be misinterpreted as HuggingFace repo IDs and throw "Repo id must be in the form 'repo_name'" errors.

### Step 5: Create Watch Directories

```bash
cd ..  # Back to project root
mkdir -p watch_data/documents watch_data/images
```

Drop any `.txt`, `.pdf`, `.docx`, `.jpg`, `.png` files here and they'll be auto-processed by the watchdog.

### Step 6: Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the Application

You need **3 processes** running:

### Terminal 1: Ollama (if not already running as a service)

```bash
ollama serve
# Verify: curl http://localhost:11434/api/tags
```

### Terminal 2: Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend starts at **http://localhost:8000**
- Swagger docs: **http://localhost:8000/docs**
- Health check: **http://localhost:8000/health**
- Watchdog auto-starts on configured `WATCH_DIRS`
- First request loads ML models (30-60s), subsequent requests are fast

### Terminal 3: Frontend

```bash
cd frontend
npm run dev
```

The frontend starts at **http://localhost:5173**.

### Quick Test

```bash
# Store a text note
curl -X POST http://localhost:8000/api/store/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text content here", "title": "My Note"}'

# Search
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "search terms", "top_k": 5}'

# RAG Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Ask a question about your stored content"}'
```

---

## Common Troubleshooting

| Issue | Fix |
|---|---|
| **Frontend shows "Offline"** | Ensure backend is running on port 8000. Check `http://localhost:8000/health` |
| **Chat keeps spinning / never responds** | Ensure Ollama is running (`curl http://localhost:11434/api/tags`). Pull model if missing: `ollama pull granite3.1-dense:8b` |
| **First request is very slow (30-60s)** | Normal — ML models load lazily on first use. Subsequent requests are fast |
| **"Repo id must be in the form 'repo_name'"** | Your `SUMMARIZER_MODEL` path is relative. Change to absolute path starting with `/` |
| **Server hangs / becomes unresponsive** | The embedder may be stuck on MPS. Code auto-falls back to CPU, but restart the server if needed |
| **Stats show 0 documents** | The watchdog processes files in the background. Check `backend/logs/main.log` for progress |
| **Bookmark sync takes forever** | Bookmark sync runs in background. Check progress at `http://localhost:8000/api/bookmarks/status` |
| **Playwright scraping fails** | Run `playwright install chromium` in your venv. Some sites block headless browsers (Cloudflare) |

---

## API Reference

All endpoints are prefixed with `/api`.

### Store Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/store/url` | `{"url": "https://..."}` | Scrape URL, summarize, store |
| POST | `/api/store/text` | `{"text": "...", "title": "..."}` | Store a text note |
| POST | `/api/store/file` | `multipart/form-data` (file) | Upload image/PDF/DOCX/TXT |
| POST | `/api/store/path` | `?path=/local/file.pdf` | Process a local file path |

### Search & Chat

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/search` | `{"query": "...", "top_k": 5}` | Semantic search (hybrid) |
| POST | `/api/chat` | `{"query": "...", "top_k": 5}` | RAG-powered Q&A |

### Bookmark Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/bookmarks/preview` | Preview Chrome bookmarks without ingesting |
| POST | `/api/bookmarks/sync` | Parse and ingest all Chrome bookmarks |

### Watchdog (File System Monitoring)

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/watchdog/start` | `{"directories": ["~/path1", "~/path2"]}` | Start auto-ingestion |
| POST | `/api/watchdog/stop` | — | Stop the watchdog |

### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stats` | Collection stats (total docs) |
| DELETE | `/api/entry/{doc_id}` | Delete a stored entry |

---

## Frontend Pages

### Home (`/`)
- **Dashboard**: Shows total document count
- **Upload Panel**: Three tabs — URL, Text, File upload
- **AI Chat**: RAG-powered Q&A interface with message bubbles and source citations

### Search (`/search`)
- Full-page semantic search bar
- Result cards showing: summary, source type badge, similarity score, tags, source link

### Settings (`/settings`)
- **File Watchdog**: Configure directories to auto-monitor for new files
- **Bookmark Sync**: Preview and import Chrome bookmarks

---

## Pipeline Details

### Layer 1 — Ingestion

| Component | File | How It Works |
|-----------|------|-------------|
| **Bookmark Sync** | `bookmark_sync.py` | Parses Chrome's `Bookmarks` JSON file recursively, extracts URLs with titles, folders, and timestamps |
| **File Watchdog** | `watchdog_agent.py` | Uses `watchdog` library to monitor directories. On file creation, pushes to async queue. Background consumer processes the queue |
| **API Router** | `router.py` | 12 FastAPI endpoints. File uploads saved to `uploads/` dir. Routes to appropriate extraction based on file type |

### Layer 2 — Extraction

| Component | File | How It Works |
|-----------|------|-------------|
| **Web Scraper** | `web_scraper.py` | Tries Trafilatura first (fast, static HTML). If < 50 chars extracted, falls back to Playwright (headless Chromium, handles SPAs) |
| **OCR Pipeline** | `ocr_pipeline.py` | Runs EasyOCR first → if < 20 chars, tries Tesseract → returns `(text, method)`. Method is `"easyocr"`, `"tesseract"`, `"combined"`, or `"none"` |
| **Document Parser** | `document_parser.py` | Routes by extension: `.pdf` → PyPDF2, `.docx` → python-docx, `.txt/.md/.csv/.json` → direct read |
| **Image Captioning** | `image_captioning.py` | Loads BLIP base model + LoRA adapter (r=16, alpha=32). Generates captions with `max_new_tokens=100`. Falls back to base BLIP if no fine-tuned weights found |

### Layer 3 — AI Processing

| Component | File | How It Works |
|-----------|------|-------------|
| **Summarizer** | `summarizer.py` | Smart truncation at sentence boundaries (max 2000 chars) → T5 seq2seq generation with beam search (4 beams), repetition penalty 1.2 |
| **Embedder** | `embedder.py` | BGE-base-en-v1.5 via SentenceTransformers. Produces 768-dim normalized embeddings. Supports batch encoding |
| **Tagger** | `tagger.py` | Prompts T5 with "Generate N short topic tags..." → parses comma-separated output → cleans and deduplicates |

### Layer 4 — Storage & Retrieval

| Component | File | How It Works |
|-----------|------|-------------|
| **Vector Store** | `vector_store.py` | ChromaDB persistent client with cosine similarity. Stores: document (summary text), embedding (768-dim), metadata (source_type, source, tags JSON, created_at). Hybrid search: dense vector search + keyword `$contains` filter with boost |
| **RAG Pipeline** | `rag_pipeline.py` | 1) Embed query → 2) Hybrid search top-K → 3) Build context string from results → 4) Prompt T5-large with context + question → 5) Return answer + sources |

### OCR Routing Logic (Image Processing)

```
Image Input
    │
    ▼
  Run OCR (EasyOCR → Tesseract)
    │
    ├── text >= 20 chars → "text-heavy image"
    │       └── Summarize with T5 → Store as "image_ocr"
    │
    └── text < 20 chars → "visual image"
            └── Generate BLIP caption → Store as "image_caption"
```

---

## Training Scripts (HPC)

These scripts are designed to run on the Northeastern HPC cluster (Nvidia H200 GPUs).

### Fine-tune T5 on XSum

```bash
cd training

# Default: T5-base on XSum, 3 epochs
python train_t5_xsum.py --epochs 3 --batch_size 16

# CNN-DailyMail dataset instead
python train_t5_xsum.py --dataset cnn_dailymail --epochs 3

# Limit training samples (for testing)
python train_t5_xsum.py --max_train_samples 5000 --epochs 1

# Full options
python train_t5_xsum.py \
  --model_name google/flan-t5-base \
  --dataset xsum \
  --output_dir ./output/t5_finetuned \
  --epochs 3 \
  --batch_size 16 \
  --lr 3e-5 \
  --max_input_length 512 \
  --max_target_length 128
```

**Output:** Saves model checkpoints per epoch + best model. Logs ROUGE scores.

### Fine-tune BLIP on Flickr8k

```bash
cd training

# Default: 5 epochs, LoRA r=16
python train_blip_flickr8k.py --epochs 5 --batch_size 32

# Full options
python train_blip_flickr8k.py \
  --output_dir ./output/blip_finetuned \
  --epochs 5 \
  --batch_size 128 \
  --lr 5e-5 \
  --lora_r 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05
```

**Output:** Saves LoRA adapter weights per epoch + best model. Copy `best/` contents to `models/blip_finetuned/` for inference.

### Evaluate Models

```bash
cd training

# Evaluate T5 summarization
python evaluate.py --task summarization --model_path ./output/t5_finetuned

# Evaluate BLIP captioning
python evaluate.py --task captioning --model_path ./output/blip_finetuned/best

# Custom sample size
python evaluate.py --task summarization --model_path ./output/t5_finetuned --max_samples 1000
```

**Metrics:** ROUGE-1, ROUGE-2, ROUGE-L for summarization. BLEU + ROUGE-L for captioning.

---

## Configuration

### Environment Variables (`.env`)

```ini
# Device: auto (detects CUDA → MPS → CPU), cuda, mps, cpu
DEVICE_PREFERENCE=auto

# ChromaDB vector database
CHROMA_PERSIST_DIR=./chroma_data       # Where ChromaDB stores data
CHROMA_COLLECTION=info_store           # Collection name

# Model paths
BLIP_MODEL_PATH=../models/blip_finetuned   # Fine-tuned BLIP LoRA weights
SUMMARIZER_MODEL=google/flan-t5-base       # Summarization model (or local path)
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5      # Embedding model
RAG_LLM_MODEL=google/flan-t5-large         # RAG answer generation model

# Server
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### Using Fine-tuned Models

After training on HPC, copy the model outputs:

```bash
# T5 summarizer — point SUMMARIZER_MODEL to local path
cp -r training/output/t5_finetuned backend/models/t5_finetuned
# Then set in .env: SUMMARIZER_MODEL=../models/t5_finetuned

# BLIP captioning — copy LoRA adapter
cp training/output/blip_finetuned/best/* models/blip_finetuned/
```

### Device Detection

The system auto-detects the best available device:
1. **CUDA** — Nvidia GPU (HPC / desktop GPU)
2. **MPS** — Apple Silicon (M1/M2/M3/M4 Mac)
3. **CPU** — Fallback

Note: BLIP and some operations fall back to CPU on MPS due to operator support limitations.

---

## Docker Deployment

```bash
# Build and run both services
docker-compose up --build

# Or run in background
docker-compose up --build -d

# Stop
docker-compose down
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

The Docker setup includes Tesseract OCR and Playwright Chromium pre-installed.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS | ChatGPT-style chat interface |
| **Backend** | FastAPI, Uvicorn | REST API with async support |
| **Summarization** | Fine-tuned T5-base (CNN/DailyMail, H200) | Text summarization + tag generation |
| **RAG Q&A** | IBM Granite 3.1 Dense 8B via Ollama | Grounded conversational answers (no hallucination) |
| **Image Captioning** | Salesforce BLIP + LoRA (PEFT) | Visual image descriptions |
| **Embeddings** | BAAI BGE-base-en-v1.5 | 768-dim semantic embeddings (MTEB benchmark leader) |
| **Vector DB** | ChromaDB | Persistent vector storage with hybrid search |
| **Web Scraping** | Playwright + Trafilatura | JS-heavy SPA + static HTML extraction |
| **OCR** | EasyOCR + Tesseract | Text extraction from images |
| **Document Parsing** | PyPDF2 + python-docx | PDF and DOCX text extraction |
| **File Monitoring** | Watchdog | Auto-ingest files from watched directories |
| **Training** | HuggingFace Transformers, PEFT | Fine-tuning on HPC (H200 GPUs) |
| **Evaluation** | ROUGE, BLEU | Standard NLP metrics |

---

## Logs

Backend logs are stored in `backend/logs/` with rotating file handlers (5MB max, 3 backups):
- `main.log` — Server lifecycle events
- `api_router.log` — API request handling
- `summarizer.log` — Summarization operations
- `embedder.log` — Embedding generation
- `web_scraper.log` — URL extraction attempts
- `ocr_pipeline.log` — OCR processing
- `vector_store.log` — ChromaDB operations
- `rag_pipeline.log` — RAG query/answer flow

---

## Datasets

| Dataset | Size | Used For |
|---------|------|----------|
| **Flickr8k** | 8K images + captions | BLIP fine-tuning (80/10/10 split) |
| **XSum** | 226K articles | T5 summarization fine-tuning |
| **CNN-DailyMail** | 300K articles | T5 summarization fine-tuning (alternative) |
| **LightShot13k** | 13K screenshots | BLIP evaluation and inference testing |
