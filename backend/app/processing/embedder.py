from sentence_transformers import SentenceTransformer
from app.config import settings, DEVICE
from app.utils.logger import get_logger

logger = get_logger("embedder")

_model = None


def _load_model():
    global _model
    if _model is not None:
        return

    device = DEVICE if DEVICE != "mps" else "cpu"
    logger.info(f"Loading embedding model: {settings.embedding_model}")
    _model = SentenceTransformer(settings.embedding_model, device=device)
    logger.info(f"Embedding model loaded on {device}")


def embed_text(text: str) -> list[float]:
    """Generate 768-dim embedding for a text string."""
    _load_model()
    embedding = _model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts."""
    _load_model()
    embeddings = _model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()
