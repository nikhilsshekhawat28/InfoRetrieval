# 04 — Data Models

## Backend: Pydantic Schemas (`app/models/schemas.py`)

All request and response bodies are validated using **Pydantic v2** models.

---

### Request Models

#### `StoreURLRequest`
```python
class StoreURLRequest(BaseModel):
    url: str                    # The URL to scrape and index
    tags: list[str] = []        # Optional user-supplied tags
```

#### `StoreTextRequest`
```python
class StoreTextRequest(BaseModel):
    text: str                   # Raw text content
    title: str = ""             # Optional display title
    tags: list[str] = []        # Optional user-supplied tags
```

#### `StoreFileRequest`
```python
# Used internally after multipart upload is decoded
class StoreFileRequest(BaseModel):
    file_path: str              # Absolute path to uploaded/local file
    tags: list[str] = []
```

#### `SearchRequest`
```python
class SearchRequest(BaseModel):
    query: str                  # Natural language search query
    top_k: int = 5              # Number of results to return
    source_type: str | None = None  # Filter by type (optional)
```

#### `ChatRequest`
```python
class ChatRequest(BaseModel):
    query: str                  # User question
    top_k: int = 5              # Number of KB results to retrieve
    evaluate: bool = False      # Whether to compute RAGAS metrics
```

#### `BookmarkSyncRequest`
```python
class BookmarkSyncRequest(BaseModel):
    bookmark_path: str | None = None  # Override default Bookmarks path
    max_bookmarks: int = 500          # Limit to prevent runaway sync
```

#### `WatchdogConfigRequest`
```python
class WatchdogConfigRequest(BaseModel):
    watch_dirs: list[str]       # Directories to monitor
```

---

### Response Models

#### `StoredItem`
The core result item returned from search, chat, and ingestion:
```python
class StoredItem(BaseModel):
    id: str                     # ChromaDB document UUID
    summary: str                # T5-generated summary (display text)
    source_type: str            # "document"|"url"|"image_caption"|"text"|"bookmark"|"image_ocr"
    source: str                 # Original file path or URL
    tags: list[str]             # Auto-generated or user tags
    distance: float             # Cosine distance (0=identical, 2=opposite)
    rerank_score: float = 0.0   # Cross-encoder score (higher = more relevant)
    rrf_score: float = 0.0      # RRF fusion score
    parent_id: str = ""         # UUID shared by all chunks of same document
    chunk_index: int = -1       # Position in document (0-based)
    chunk_text: str = ""        # The actual indexed chunk text
```

#### `EvaluationScores`
```python
class EvaluationScores(BaseModel):
    faithfulness: float         # 0-1: Are claims grounded in retrieved context?
    answer_relevancy: float     # 0-1: Does answer address the query?
    context_precision: float    # 0-1: Are retrieved chunks relevant?
    overall: float              # Weighted average of above three
```

#### `SearchResponse`
```python
class SearchResponse(BaseModel):
    results: list[StoredItem]
    query: str
    total: int
```

#### `ChatResponse`
```python
class ChatResponse(BaseModel):
    answer: str                 # LLM-generated answer text
    sources: list[StoredItem]   # Top retrieved results used as context
    crag_triggered: bool        # Whether query was rewritten via CRAG
    query_rewritten: str | None = None   # The rewritten query (if CRAG)
    evaluation: EvaluationScores | None = None  # Present only if evaluate=True
```

#### `IngestResponse`
```python
class IngestResponse(BaseModel):
    id: str | list[str]         # Single ID or list of chunk IDs
    summary: str                # Generated summary
    source_type: str
    tags: list[str]
    chunk_count: int            # Number of chunks created
    message: str = "success"
```

#### `StatsResponse`
```python
class StatsResponse(BaseModel):
    total_documents: int        # Total ChromaDB entries (chunks)
    total_chunks: int           # Entries that have a parent_id
    unique_parents: int         # Distinct documents
    collection_name: str
    by_type: dict[str, int]     # Count per source_type
    file_counts: dict           # {"images_on_disk": N, "documents_on_disk": N, "bookmarks": N}
```

---

## ChromaDB Metadata Schema

Every chunk stored in ChromaDB carries this metadata dict:

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | `str` | One of: `"document"`, `"url"`, `"image_caption"`, `"image_ocr"`, `"text"`, `"bookmark"` |
| `source` | `str` | File system path (absolute) or URL |
| `tags` | `str` | JSON-encoded array: `'["tag1","tag2"]'` |
| `created_at` | `str` | ISO 8601 datetime: `"2026-04-12T10:30:00.000000"` |
| `parent_id` | `str` | UUID shared by all chunks of one document. Empty for legacy non-chunked entries |
| `chunk_index` | `int` | Zero-based position of this chunk within the document |
| `total_chunks` | `int` | Total number of chunks in the parent document |
| `summary` | `str` | T5 summary (max 1000 chars), stored only in chunked entries |
| `full_text_length` | `int` | Character count of the full extracted text |

> **Note:** ChromaDB metadata values must be primitive types (str, int, float, bool). Lists are serialized as JSON strings.

---

## Frontend TypeScript Types (`src/lib/types.ts`)

### `ChatMessage`
The in-memory message object for UI state:
```typescript
interface ChatMessage {
  id: string;                    // UUID for React key
  role: "user" | "assistant" | "system";
  content: string;               // Raw text (markdown for assistant)
  sources?: Source[];            // Retrieved sources (assistant only)
  searchResults?: Source[];      // Search mode results (assistant only)
  evaluation?: EvaluationScores; // Quality scores (if evaluate=true)
  cragTriggered?: boolean;       // Whether CRAG rewrote the query
  timestamp: Date;               // Client-side timestamp for display
}
```

### `Source`
Maps to `StoredItem` from the backend:
```typescript
interface Source {
  id: string;
  summary: string;
  source_type: string;
  source: string;
  tags: string[];
  distance: number;
  rerank_score?: number;
  rrf_score?: number;
  parent_id?: string;
  chunk_index?: number;
  chunk_text?: string;
}
```

### `EvaluationScores`
```typescript
interface EvaluationScores {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  overall: number;
}
```

### `ChatResponse` (API response shape)
```typescript
interface ChatResponse {
  answer: string;
  sources: Source[];
  crag_triggered: boolean;
  query_rewritten?: string;
  evaluation?: EvaluationScores;
}
```

### `StatsResponse`
```typescript
interface StatsResponse {
  total_documents: number;
  total_chunks: number;
  unique_parents: number;
  collection_name: string;
  by_type: Record<string, number>;
  file_counts: {
    images_on_disk: number;
    documents_on_disk: number;
    bookmarks: number;
  };
}
```

### Enum-like Constants
```typescript
type MessageRole = "user" | "assistant" | "system";
type ChatMode = "chat" | "search";   // (chat = RAG, search = semantic search only)

const SOURCE_TYPE_ICONS: Record<string, string> = {
  document:       "📄",
  url:            "🔗",
  image_caption:  "🖼️",
  text:           "📝",
  bookmark:       "🔖",
  image_ocr:      "👁️",
};
```

---

## Config Model (`app/config.py`)

The `Settings` class (Pydantic `BaseSettings`) exposes all env variables as typed attributes:

```python
class Settings(BaseSettings):
    # Device
    device_preference: str = "auto"   # "auto" | "cuda" | "mps" | "cpu"
    
    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "info_store"
    
    # Model paths
    blip_model_path: str = "../models/blip_finetuned"
    summarizer_model: str = "google/flan-t5-base"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    rag_llm_model: str = "granite3.1-dense:2b"
    
    # Chunking
    chunk_size: int = 300
    chunk_overlap: int = 80
    
    # RAG behavior
    enable_contextual_retrieval: bool = False
    
    # File watching
    watch_dirs: str = ""             # Comma-separated paths
    bookmark_path: str = ""          # Chrome Bookmarks file path
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()              # Singleton imported everywhere
DEVICE = _get_device(settings)    # Resolved: "cuda" | "mps" | "cpu"
```
