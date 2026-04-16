import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ingestion.router import router, _process_and_store, _process_image
from app.retrieval.rag_pipeline import _warmup_ollama
from app.ingestion.watchdog_agent import file_queue, is_image_file, is_document_file
from app.extraction.document_parser import parse_document
from app.storage.vector_store import is_source_indexed
from app.utils.logger import get_logger

logger = get_logger("main")

# Thread pool for CPU-heavy watchdog processing so it doesn't block the API
_watchdog_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="watchdog")


def _process_file_sync(file_path: str):
    """Process a single file using the enhanced chunked pipeline.

    Skips files already indexed to prevent duplicate entries on server restart.
    """
    if is_source_indexed(file_path):
        logger.debug(f"Skipping already-indexed file: {file_path}")
        return

    if is_image_file(file_path):
        _process_image(file_path, file_path)
        logger.info(f"Auto-stored image: {file_path}")
    elif is_document_file(file_path):
        text = parse_document(file_path)
        _process_and_store(text, source_type="document", source=file_path)
        logger.info(f"Auto-stored document: {file_path}")
    else:
        return


async def watchdog_consumer():
    """Background task: process files detected by the watchdog."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            file_path = await asyncio.wait_for(file_queue.get(), timeout=5.0)
            logger.info(f"Processing watchdog file: {file_path}")

            try:
                # Run in thread pool so API stays responsive
                await loop.run_in_executor(_watchdog_pool, _process_file_sync, file_path)
            except Exception as e:
                logger.error(f"Watchdog processing error for {file_path}: {e}")

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Watchdog consumer error: {e}")
            await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    logger.info("InfoStore v2 starting up...")

    # Start watchdog consumer as background task
    consumer_task = asyncio.create_task(watchdog_consumer())

    # Warm up Ollama model in background so first query isn't slow
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _warmup_ollama)

    # Auto-start watchdog if WATCH_DIRS configured
    if settings.watch_dirs:
        dirs = [d.strip() for d in settings.watch_dirs.split(",") if d.strip()]
        if dirs:
            from app.ingestion.watchdog_agent import start_watchdog
            started = start_watchdog(dirs)
            if started:
                logger.info(f"Auto-started watchdog on: {dirs}")
            else:
                logger.warning("Failed to auto-start watchdog")

    yield

    # Cleanup
    consumer_task.cancel()
    from app.ingestion.watchdog_agent import stop_watchdog
    stop_watchdog()
    logger.info("InfoStore v2 shut down.")


app = FastAPI(
    title="InfoStore v2 - Multimodal AI Knowledge Base",
    description=(
        "A multimodal AI system for unified content summarization and retrieval. "
        "Supports URLs, images, PDFs, DOCX, text notes with semantic search and RAG."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routes
app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
