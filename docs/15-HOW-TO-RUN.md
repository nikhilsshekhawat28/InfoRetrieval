# 15 — How to Run

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10 or 3.11 | Backend runtime |
| Node.js | 18 or 20 | Frontend runtime |
| Ollama | Latest | Local LLM inference |
| Git | Any | Source control |

### Optional (for full functionality)

| Software | Purpose |
|----------|---------|
| CUDA Toolkit 11.8+ | GPU acceleration |
| Tesseract OCR | Fallback OCR (EasyOCR is primary) |
| Google Chrome | Bookmark sync |

---

## Local Development Setup

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd "proj jsr"
```

### Step 2: Set Up Ollama

```bash
# Install Ollama (Windows)
# Download from https://ollama.com and run installer

# Start Ollama service
ollama serve

# Pull the model (in a separate terminal)
ollama pull granite3.1-dense:2b

# Verify it works
ollama run granite3.1-dense:2b "What is 2+2?"
```

Keep `ollama serve` running in a terminal throughout development.

### Step 3: Set Up the Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for web scraping fallback)
playwright install chromium
```

### Step 4: Configure Environment

```bash
# Copy the template
cp .env.example .env

# Edit .env with your values
# Required changes:
#   WATCH_DIRS - Point to your watch_data directories
#   BOOKMARK_PATH - Point to your Chrome Bookmarks file
```

**Minimal `.env` for first run:**
```ini
DEVICE_PREFERENCE=auto
CHROMA_PERSIST_DIR=./chroma_data
CHROMA_COLLECTION=info_store
BLIP_MODEL_PATH=../models/blip_finetuned
SUMMARIZER_MODEL=google/flan-t5-base
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
RAG_LLM_MODEL=granite3.1-dense:2b
CHUNK_SIZE=300
CHUNK_OVERLAP=80
ENABLE_CONTEXTUAL_RETRIEVAL=False
WATCH_DIRS=E:/path/to/your/watch_data/documents,E:/path/to/your/watch_data/images
BOOKMARK_PATH=C:/Users/YourName/AppData/Local/Google/Chrome/User Data/Default/Bookmarks
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### Step 5: Start the Backend

```bash
# From backend/ directory (with venv activated)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`--reload` enables auto-restart on code changes (development mode only).

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started reloader process
INFO:     InfoStore starting up...
INFO:     ChromaDB collection 'info_store' ready (0 documents)
INFO:     Watchdog consumer started
INFO:     Auto-started watchdog on 2 directories
```

### Step 6: Set Up the Frontend

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in 350 ms
  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Step 7: Open the Application

Navigate to `http://localhost:5173` in your browser.

---

## First-Run Content Loading

On first run, the knowledge base is empty. To populate it:

### Option A: Add files to watch_data/
```bash
# Copy PDFs, documents, or images to:
watch_data/documents/    # for PDFs, DOCX, TXT
watch_data/images/       # for JPG, PNG
```

The watchdog will automatically detect and index new files. Watch the backend logs:
```bash
tail -f backend/logs/api_router.log
```

### Option B: Sync Chrome Bookmarks
1. Click the sidebar toggle (hamburger icon)
2. Click "Sync Bookmarks"
3. Wait for the sync to complete (shown in the stats bar)

### Option C: Add a URL manually
1. Open the sidebar
2. Click "Add URL"
3. Enter a URL and click "Add"

### Option D: Upload a file
1. Open the sidebar
2. Click "Upload File"
3. Select a PDF, DOCX, TXT, image, etc.

---

## Production Build (Frontend)

```bash
cd frontend
npm run build
# Output: frontend/dist/

# Preview the production build locally
npm run preview
```

---

## Docker Deployment

### Using Docker Compose

```bash
# From project root
docker-compose up --build

# Services:
# - backend: http://localhost:8000
# - frontend: http://localhost:5173
```

### Docker Notes
- Set `DEVICE_PREFERENCE=cpu` in docker-compose environment unless you configure NVIDIA Docker
- The `chroma_data/`, `models/`, and `watch_data/` directories are mounted as volumes
- Ollama must run on the host machine (not in Docker) unless you add an Ollama service to compose

### Adding Ollama to Docker Compose
```yaml
services:
  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: [ollama_data:/root/.ollama]
    # For GPU: add runtime: nvidia

  backend:
    # ... (change OLLAMA_URL to http://ollama:11434/api/generate)
    environment:
      - OLLAMA_URL=http://ollama:11434/api/generate
    depends_on: [ollama]
```

---

## Troubleshooting

### Backend won't start

**Error:** `ModuleNotFoundError: No module named 'app'`
```bash
# Make sure you're in backend/ and venv is activated
cd backend
source venv/bin/activate   # or venv\Scripts\activate on Windows
uvicorn app.main:app ...
```

**Error:** `Port 8000 already in use`
```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

### Ollama Issues

**Error:** `Connection refused on localhost:11434`
```bash
# Make sure Ollama is running
ollama serve

# Verify model is available
ollama list
```

**Error:** `model 'granite3.1-dense:2b' not found`
```bash
ollama pull granite3.1-dense:2b
# This downloads ~1.5GB
```

**Slow responses (>30 seconds)**
- Set `DEVICE_PREFERENCE=cuda` if you have NVIDIA GPU
- Or accept CPU inference (~20-60s per response for 2B model)

### ChromaDB Issues

**Error:** `Collection not found`
```bash
# ChromaDB auto-creates the collection on startup. 
# If you see this, the data directory may be corrupted.
rm -rf backend/chroma_data/
# Restart backend — it will recreate empty collection
# Then re-index your files
```

**Error:** `hnsw: unable to resize, not enough memory`
- Reduce `top_k` in queries
- Or restart the backend to free memory

### Frontend Issues

**Error:** `Failed to fetch` / `Network Error`
- Check backend is running on port 8000
- Check CORS: backend must be on `localhost:8000`, not `127.0.0.1:8000`

**Blank page / White screen**
```bash
cd frontend
npm run build   # Check for TypeScript/build errors
```

### OCR Issues

**Error:** `EasyOCR download error`
- EasyOCR downloads its models on first use (~500MB)
- Ensure internet connection on first run
- Models cached at `~/.EasyOCR/model/`

**Error:** `Tesseract not found`
```bash
# Windows: download installer from GitHub
# https://github.com/UB-Mannheim/tesseract/wiki

# macOS
brew install tesseract

# Linux
sudo apt install tesseract-ocr
```

### Model Loading Issues

**BLIP LoRA not loading**
- Check `BLIP_MODEL_PATH` in `.env` points to the correct directory
- The directory should contain `adapter_config.json` and `adapter_model.safetensors`
- If missing, the system falls back to base BLIP (no fine-tuning)

**T5 model not found**
- If `SUMMARIZER_MODEL` is a local path, verify it contains `config.json` and `model.safetensors`
- If it's a HuggingFace ID (`google/flan-t5-base`), internet access is needed on first load (cached after)

---

## Environment-Specific Configurations

### Windows (Current deployment)
```ini
DEVICE_PREFERENCE=auto     # Will use CUDA if NVIDIA GPU available
WATCH_DIRS=E:/path/to/docs,E:/path/to/images   # Windows-style paths work
BOOKMARK_PATH=C:/Users/username/AppData/Local/Google/Chrome/User Data/Default/Bookmarks
```

### macOS (Apple Silicon)
```ini
DEVICE_PREFERENCE=mps      # Use Apple GPU
WATCH_DIRS=/Users/username/Documents/watch_docs,/Users/username/Pictures/watch_images
BOOKMARK_PATH=/Users/username/Library/Application Support/Google/Chrome/Default/Bookmarks
```

### Linux
```ini
DEVICE_PREFERENCE=cuda     # If NVIDIA GPU
WATCH_DIRS=/home/username/docs,/home/username/images
BOOKMARK_PATH=/home/username/.config/google-chrome/Default/Bookmarks
```
