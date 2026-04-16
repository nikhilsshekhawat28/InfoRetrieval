import os
import torch
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Device
    device_preference: str = "auto"

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "chroma_data")
    chroma_collection: str = "info_store"

    # Models
    blip_model_path: str = str(BASE_DIR.parent / "models" / "blip_finetuned")
    summarizer_model: str = str(BASE_DIR / "models" / "t5_finetuned" / "final_model_h200")
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rag_llm_model: str = "google/flan-t5-large"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50

    # RAG
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "granite3.1-dense:2b"
    relevance_threshold: float = 0.45
    enable_contextual_retrieval: bool = True
    enable_evaluation: bool = False

    # Watchdog
    watch_dirs: str = ""
    bookmark_path: str = os.path.expanduser(
        "~/Library/Application Support/Google/Chrome/Default/Bookmarks"
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()


def get_device() -> str:
    pref = settings.device_preference.lower()
    if pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


DEVICE = get_device()
logging.info(f"Using device: {DEVICE}")
