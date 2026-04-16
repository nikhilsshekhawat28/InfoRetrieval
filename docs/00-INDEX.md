# InfoStore v2 — Documentation Index

**Project:** InfoStore v2 — Multimodal AI Knowledge Base  
**Course:** CS5130 · Northeastern University · Spring 2026  
**Team:** Vishnu Purohitham · Nimish Poonekar · Nikhil Shekhawat · Rajarshi Dey  

---

## Table of Contents

| # | Document | Description |
|---|----------|-------------|
| [00](./00-INDEX.md) | **Index** | This file — master table of contents |
| [01](./01-PROJECT-OVERVIEW.md) | **Project Overview** | Goals, scope, key features, technology summary |
| [02](./02-FOLDER-STRUCTURE.md) | **Folder Structure** | Annotated directory tree, every file explained |
| [03](./03-ARCHITECTURE.md) | **Architecture** | System design, component interactions, data flow diagrams |
| [04](./04-DATA-MODELS.md) | **Data Models** | Pydantic schemas, ChromaDB metadata schema, TypeScript types |
| [05](./05-API-ROUTES.md) | **API Routes** | Full endpoint reference: URL, method, request body, response |
| [06](./06-LAYERS-AND-COMPONENTS.md) | **Layers & Components** | Every backend module and frontend component documented |
| [07](./07-AUTH.md) | **Auth & Security** | Current auth posture, CORS, future considerations |
| [08](./08-INTEGRATIONS.md) | **External Integrations** | Ollama, wttr.in, DuckDuckGo, Chrome Bookmarks, Playwright |
| [09](./09-CONFIG-AND-ENV.md) | **Configuration & Env** | All `.env` variables, `config.py`, device detection |
| [10](./10-FRONTEND.md) | **Frontend** | React app structure, state management, UI components, theming |
| [11](./11-AI-ML-MODELS.md) | **AI/ML Models** | BLIP, T5, BGE, Cross-Encoder, Granite — specs & fine-tuning |
| [12](./12-BACKGROUND-JOBS.md) | **Background Jobs** | Watchdog agent, async queue, file consumer, bookmark sync |
| [13](./13-ERROR-HANDLING-AND-LOGGING.md) | **Error Handling & Logging** | Logger setup, error strategies, fallback chains |
| [14](./14-TESTING.md) | **Testing** | Playwright E2E, Vitest unit tests, backend test approach |
| [15](./15-HOW-TO-RUN.md) | **How to Run** | Local dev, Docker, environment setup, troubleshooting |
| [16](./16-BUSINESS-LOGIC-FLOWS.md) | **Business Logic Flows** | Step-by-step walkthroughs of every major user interaction |

---

## Quick Links by Role

### I want to run the app locally
→ [15-HOW-TO-RUN.md](./15-HOW-TO-RUN.md)

### I want to understand the overall design
→ [01-PROJECT-OVERVIEW.md](./01-PROJECT-OVERVIEW.md) then [03-ARCHITECTURE.md](./03-ARCHITECTURE.md)

### I want to add a new API endpoint
→ [05-API-ROUTES.md](./05-API-ROUTES.md) then [06-LAYERS-AND-COMPONENTS.md](./06-LAYERS-AND-COMPONENTS.md)

### I want to understand how RAG works in this system
→ [16-BUSINESS-LOGIC-FLOWS.md](./16-BUSINESS-LOGIC-FLOWS.md) § RAG Query Flow

### I want to change model configuration
→ [09-CONFIG-AND-ENV.md](./09-CONFIG-AND-ENV.md) then [11-AI-ML-MODELS.md](./11-AI-ML-MODELS.md)

### I want to add a new content source type
→ [12-BACKGROUND-JOBS.md](./12-BACKGROUND-JOBS.md) then [16-BUSINESS-LOGIC-FLOWS.md](./16-BUSINESS-LOGIC-FLOWS.md)

### I want to understand the frontend
→ [10-FRONTEND.md](./10-FRONTEND.md)

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (Browser)                           │
│              React + Vite + Tailwind @ :5173                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (fetch)
┌───────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend @ :8000                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Ingestion  │  │  Retrieval │  │  Storage   │  │  Utils   │  │
│  │  Router    │  │  RAG       │  │  Vector    │  │  Logger  │  │
│  │  Watchdog  │  │  Pipeline  │  │  Store     │  │  Config  │  │
│  │  Bookmarks │  │  Evaluator │  │  ChromaDB  │  │          │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │ Extraction │  │ Processing │  │  Models    │                 │
│  │  DocParser │  │  Chunker   │  │  Schemas   │                 │
│  │  ImageCap  │  │  Embedder  │  │  T5 local  │                 │
│  │  OCR       │  │  Reranker  │  │  BLIP LoRA │                 │
│  │  Scraper   │  │  Summarizer│  │            │                 │
│  └────────────┘  └────────────┘  └────────────┘                 │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
    ┌──────────▼────────┐      ┌──────────▼────────┐
    │   ChromaDB        │      │   Ollama           │
    │   (Persistent)    │      │   granite3.1:2b    │
    └───────────────────┘      └───────────────────┘
```

---

*Generated: April 2026 · InfoStore v2*
