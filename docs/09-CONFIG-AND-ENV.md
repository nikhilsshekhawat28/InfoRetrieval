# 09 — Configuration & Environment

## Environment File: `.env`

The backend reads all configuration from `backend/.env`. The `Settings` class in `config.py` loads these via Pydantic Settings.

A template is provided in `backend/.env.example`.

---

## All Environment Variables

### Device

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_PREFERENCE` | `auto` | Compute device for ML models. Options: `auto`, `cuda`, `mps`, `cpu`. `auto` picks the best available. |

**Device resolution logic:**
- `auto`: tries `cuda` → `mps` → `cpu`
- `cuda`: uses NVIDIA GPU if available, else falls back to CPU
- `mps`: uses Apple Silicon GPU if available, else falls back to CPU
- `cpu`: always uses CPU

---

### ChromaDB

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_PERSIST_DIR` | `./chroma_data` | Directory where ChromaDB stores its data (relative to `backend/`) |
| `CHROMA_COLLECTION` | `info_store` | Name of the ChromaDB collection |

ChromaDB is auto-created at startup if the directory doesn't exist. The collection is created with `hnsw:space=cosine`.

---

### AI/ML Models

| Variable | Default | Description |
|----------|---------|-------------|
| `BLIP_MODEL_PATH` | `../models/blip_finetuned` | Path to fine-tuned BLIP LoRA adapter. Falls back to base BLIP if not found. |
| `SUMMARIZER_MODEL` | `google/flan-t5-base` | T5 model for summarization. Can be a HuggingFace model ID or local path. |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | SentenceTransformer model for embeddings. |
| `RAG_LLM_MODEL` | `granite3.1-dense:2b` | Ollama model name for answer generation. |

**Actual values in production `.env`:**
```ini
BLIP_MODEL_PATH=../models/blip_finetuned
SUMMARIZER_MODEL=google/flan-t5-base
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
RAG_LLM_MODEL=granite3.1-dense:2b
```

---

### Text Chunking

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `300` | Target word count per chunk |
| `CHUNK_OVERLAP` | `80` | Words of overlap between consecutive chunks |

**Tuning guidance:**
- Larger `CHUNK_SIZE` → more context per chunk, fewer chunks, but may exceed cross-encoder token limits (~512 tokens ≈ 380 words)
- Larger `CHUNK_OVERLAP` → richer context continuity, but more storage and slower indexing
- Current values (300/80) are optimized for the cross-encoder's 512-token limit

---

### Advanced Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_CONTEXTUAL_RETRIEVAL` | `False` | Whether to add LLM-generated context prefix per chunk during indexing. Significantly improves retrieval quality but requires an Ollama call per chunk (slow for large documents). |

**Recommendation:** Keep `False` during initial indexing (faster). Enable only for selective re-indexing of high-priority documents.

---

### File Watching

| Variable | Default | Description |
|----------|---------|-------------|
| `WATCH_DIRS` | `""` | Comma-separated list of directories to monitor for new files |
| `BOOKMARK_PATH` | `""` | Absolute path to Chrome Bookmarks JSON file |

**Example values:**
```ini
WATCH_DIRS=E:/NEU/Sem 2/APP/Project/proj jsr/watch_data/documents,E:/NEU/Sem 2/APP/Project/proj jsr/watch_data/images
BOOKMARK_PATH=C:/Users/nikhi/AppData/Local/Google/Chrome/User Data/Default/Bookmarks
```

**OS-specific Chrome Bookmarks paths:**
- Windows: `C:\Users\{user}\AppData\Local\Google\Chrome\User Data\Default\Bookmarks`
- macOS: `~/Library/Application Support/Google/Chrome/Default/Bookmarks`
- Linux: `~/.config/google-chrome/Default/Bookmarks`

---

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Network interface to bind to |
| `PORT` | `8000` | Port for FastAPI/uvicorn |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## `config.py` Implementation

```python
from pydantic_settings import BaseSettings
import torch

class Settings(BaseSettings):
    device_preference: str = "auto"
    
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "info_store"
    
    blip_model_path: str = "../models/blip_finetuned"
    summarizer_model: str = "google/flan-t5-base"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    rag_llm_model: str = "granite3.1-dense:2b"
    
    chunk_size: int = 300
    chunk_overlap: int = 80
    
    enable_contextual_retrieval: bool = False
    
    watch_dirs: str = ""
    bookmark_path: str = ""
    
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False   # Env var names are case-insensitive


def _get_device(s: Settings) -> str:
    pref = s.device_preference.lower()
    if pref == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if pref == "mps":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if pref == "auto":
        if torch.cuda.is_available(): return "cuda"
        if torch.backends.mps.is_available(): return "mps"
    return "cpu"


settings = Settings()
DEVICE = _get_device(settings)
```

---

## Frontend Configuration

The frontend has no `.env` file — configuration is hardcoded in `src/lib/api.ts`:

```typescript
const API_BASE = "http://localhost:8000";
```

For a different backend URL (e.g., Docker deployment), update this constant.

**Vite environment variables** (if needed in future): Create `frontend/.env` with `VITE_` prefix variables; they are bundled at build time.

---

## Docker Configuration

`docker-compose.yml` at project root defines two services:

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DEVICE_PREFERENCE=cpu
      - CHROMA_PERSIST_DIR=/data/chroma
      - ...
    volumes:
      - ./chroma_data:/data/chroma
      - ./models:/app/models
      - ./watch_data:/watch_data
  
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    depends_on: [backend]
```

**Note:** Docker containers don't have GPU access by default. Set `DEVICE_PREFERENCE=cpu` or configure `nvidia-container-toolkit` for CUDA passthrough.
