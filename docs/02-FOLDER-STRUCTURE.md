# 02 — Folder Structure

## Root Directory

```
proj jsr/
├── docs/                          ← Technical documentation (this folder)
├── backend/                       ← Python FastAPI server
├── frontend/                      ← React + Vite client
├── models/                        ← Locally fine-tuned model weights
│   └── blip_finetuned/            ← BLIP LoRA adapter (PEFT)
├── training/                      ← Training scripts for fine-tuned models
├── watch_data/                    ← Default watchdog-monitored directories
│   ├── documents/                 ← PDFs, DOCX files to auto-index
│   └── images/                    ← Images to auto-index
├── README.md                      ← Project README
├── Challenges_and_Solutions.md    ← Engineering challenges journal
├── Challenges_and_Solutions.docx  ← Same, Word format
├── docker-compose.yml             ← Multi-service Docker config
└── .gitignore                     ← Ignores .env, venv, node_modules, chroma_data
```

---

## Backend Directory

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    ← FastAPI app, lifespan, watchdog consumer, CORS
│   ├── config.py                  ← Pydantic Settings, device detection
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py             ← All Pydantic request/response models
│   │   └── t5_finetuned/          ← Local T5 model weights
│   │       └── final_model_h200/  ← Fine-tuned checkpoint
│   │           ├── config.json
│   │           ├── generation_config.json
│   │           ├── model.safetensors   ← Actual weights (~250MB)
│   │           ├── tokenizer.json
│   │           ├── tokenizer_config.json
│   │           └── training_args.bin
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── router.py              ← FastAPI APIRouter, all /api/* endpoints
│   │   ├── bookmark_sync.py       ← Chrome Bookmarks JSON parser
│   │   └── watchdog_agent.py      ← File system watchdog (watchdog library)
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── document_parser.py     ← PDF/DOCX/TXT/MD text extraction
│   │   ├── image_captioning.py    ← BLIP model + LoRA adapter
│   │   ├── ocr_pipeline.py        ← EasyOCR → Tesseract fallback
│   │   └── web_scraper.py         ← Trafilatura → Playwright fallback
│   │
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── chunker.py             ← Sentence-aware text chunking
│   │   ├── embedder.py            ← BGE-base-en-v1.5 embeddings
│   │   ├── reranker.py            ← Cross-encoder reranking
│   │   ├── summarizer.py          ← T5 summarization with beam search
│   │   └── tagger.py              ← T5 auto-tag generation
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── rag_pipeline.py        ← Full RAG: routing, retrieval, CRAG, generation
│   │   └── evaluator.py           ← RAGAS-style metrics
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   └── vector_store.py        ← ChromaDB wrapper with hybrid search, RRF, stats
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py              ← Per-module rotating file loggers
│
├── chroma_data/                   ← ChromaDB persistence (auto-created)
│   ├── <uuid>/                    ← Collection segments
│   └── chroma.sqlite3             ← Collection metadata SQLite DB
│
├── logs/                          ← Rotating log files (auto-created)
│   ├── main.log
│   ├── api_router.log
│   ├── rag_pipeline.log
│   ├── vector_store.log
│   ├── chunker.log
│   ├── summarizer.log
│   ├── embedder.log
│   ├── reranker.log
│   ├── image_captioning.log
│   ├── ocr_pipeline.log
│   ├── document_parser.log
│   ├── tagger.log
│   ├── web_scraper.log
│   ├── bookmark_sync.log
│   └── watchdog_agent.log
│
├── uploads/                       ← Temporary uploaded files (auto-cleared)
├── .env                           ← Environment variables (git-ignored)
├── .env.example                   ← Template for .env
├── requirements.txt               ← Python dependencies
├── Dockerfile                     ← Docker image definition
└── venv/                          ← Python virtual environment (git-ignored)
```

---

## Frontend Directory

```
frontend/
├── index.html                     ← HTML entry point, mounts <div id="root">
├── package.json                   ← npm dependencies and scripts
├── package-lock.json              ← Lock file
├── vite.config.ts                 ← Vite: dev server, SWC, path aliases
├── tailwind.config.ts             ← Tailwind: dark mode, CSS variables, keyframes
├── tsconfig.json                  ← TypeScript config (strict mode)
├── tsconfig.app.json              ← App-specific TS config
├── tsconfig.node.json             ← Node tooling TS config
├── components.json                ← shadcn/ui CLI config
├── playwright.config.ts           ← E2E test config
├── playwright-fixture.ts          ← Playwright test fixtures
├── eslint.config.js               ← ESLint config
├── postcss.config.js              ← PostCSS (Tailwind integration)
│
└── src/
    ├── main.tsx                   ← React entry: renders <App /> into #root
    ├── App.tsx                    ← Root: ThemeProvider, QueryClientProvider, Router
    ├── index.css                  ← Global CSS: mesh gradient, orbs, keyframes, glass
    ├── App.css                    ← App-level CSS (minimal)
    │
    ├── lib/
    │   ├── api.ts                 ← Typed API client: all fetch calls to :8000
    │   └── types.ts               ← Shared TypeScript interfaces
    │
    ├── pages/
    │   ├── Index.tsx              ← Main chat page: layout, state, message handling
    │   └── NotFound.tsx           ← 404 page
    │
    └── components/
        ├── AppSidebar.tsx         ← Sidebar: URL/Note/File/Bookmark ingestion controls
        ├── ChatInput.tsx          ← Textarea + send button
        ├── ChatMessage.tsx        ← Message bubbles, sources, badges, copy button
        ├── NavLink.tsx            ← Navigation link component
        ├── SourceCard.tsx         ← Individual result card
        ├── StatsBar.tsx           ← Top bar: animated counters, DB status
        ├── ThemeToggle.tsx        ← Dark/light mode toggle button
        ├── WelcomeMessage.tsx     ← Initial screen with animated rings
        └── ui/                    ← shadcn/ui generated components
            ├── accordion.tsx
            ├── alert-dialog.tsx
            ├── alert.tsx
            ├── avatar.tsx
            ├── badge.tsx
            ├── button.tsx
            ├── card.tsx
            ├── checkbox.tsx
            ├── collapsible.tsx
            ├── command.tsx
            ├── context-menu.tsx
            ├── dialog.tsx
            ├── drawer.tsx
            ├── dropdown-menu.tsx
            ├── form.tsx
            ├── hover-card.tsx
            ├── input.tsx
            ├── input-otp.tsx
            ├── label.tsx
            ├── menubar.tsx
            ├── navigation-menu.tsx
            ├── pagination.tsx
            ├── popover.tsx
            ├── progress.tsx
            ├── radio-group.tsx
            ├── resizable.tsx
            ├── scroll-area.tsx
            ├── select.tsx
            ├── separator.tsx
            ├── sheet.tsx
            ├── sidebar.tsx
            ├── skeleton.tsx
            ├── slider.tsx
            ├── sonner.tsx
            ├── switch.tsx
            ├── table.tsx
            ├── tabs.tsx
            ├── textarea.tsx
            ├── toast.tsx
            ├── toaster.tsx
            ├── toggle.tsx
            ├── toggle-group.tsx
            ├── tooltip.tsx
            └── use-toast.ts
```

---

## Key File Roles at a Glance

| File | Role |
|------|------|
| `backend/app/main.py` | FastAPI app factory, CORS, lifespan hooks, watchdog consumer task |
| `backend/app/config.py` | Single source of truth for all settings, device auto-detection |
| `backend/app/ingestion/router.py` | All 12+ HTTP endpoints wired here |
| `backend/app/retrieval/rag_pipeline.py` | Heart of the system — query routing, retrieval, generation |
| `backend/app/storage/vector_store.py` | All ChromaDB interactions abstracted here |
| `backend/app/processing/chunker.py` | Text → overlapping sentence-boundary chunks |
| `frontend/src/lib/api.ts` | All backend calls from the frontend |
| `frontend/src/lib/types.ts` | Shared TS types for API responses and UI state |
| `frontend/src/pages/Index.tsx` | Top-level page component with message state |
| `frontend/src/components/ChatMessage.tsx` | Renders individual messages, sources, badges |
