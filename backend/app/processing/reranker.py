from sentence_transformers import CrossEncoder
from app.config import settings, DEVICE
from app.utils.logger import get_logger

logger = get_logger("reranker")

_model = None


def _load_model():
    global _model
    if _model is not None:
        return

    device = DEVICE if DEVICE != "mps" else "cpu"
    logger.info(f"Loading reranker model: {settings.reranker_model}")
    _model = CrossEncoder(settings.reranker_model, device=device)
    logger.info(f"Reranker loaded on {device}")


def rerank(query: str, results: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank search results using a cross-encoder model.

    Cross-encoders jointly process (query, document) pairs for precise
    relevance scoring, unlike bi-encoders which embed independently.
    """
    if not results:
        return []

    _load_model()

    pairs = [[query, r.get("chunk_text", r.get("summary", ""))] for r in results]
    scores = _model.predict(pairs)

    for i, result in enumerate(results):
        result["rerank_score"] = float(scores[i])

    reranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)
    logger.info(
        f"Reranked {len(results)} results, "
        f"top score: {reranked[0]['rerank_score']:.4f}"
    )
    return reranked[:top_k]
