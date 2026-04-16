import httpx
from app.utils.logger import get_logger

logger = get_logger("evaluator")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "granite3.1-dense:8b"


def _query_ollama(prompt: str) -> str:
    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 50},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Evaluation LLM error: {e}")
        return ""


def evaluate_faithfulness(answer: str, context: str) -> float:
    """Score 0-1: are all claims in the answer supported by the context?"""
    prompt = (
        "Rate how well the answer is supported by the context. "
        "Respond with ONLY a number between 0.0 and 1.0.\n"
        "1.0 = every claim is directly supported\n"
        "0.0 = the answer is completely fabricated\n\n"
        f"Context: {context[:2000]}\n\n"
        f"Answer: {answer}\n\n"
        "Score:"
    )
    raw = _query_ollama(prompt)
    try:
        return max(0.0, min(1.0, float(raw.strip().split()[0])))
    except (ValueError, IndexError):
        return 0.0


def evaluate_relevancy(answer: str, query: str) -> float:
    """Score 0-1: does the answer address the query?"""
    prompt = (
        "Rate how relevant the answer is to the question. "
        "Respond with ONLY a number between 0.0 and 1.0.\n"
        "1.0 = directly and completely answers the question\n"
        "0.0 = completely irrelevant\n\n"
        f"Question: {query}\n\n"
        f"Answer: {answer}\n\n"
        "Score:"
    )
    raw = _query_ollama(prompt)
    try:
        return max(0.0, min(1.0, float(raw.strip().split()[0])))
    except (ValueError, IndexError):
        return 0.0


def evaluate_context_precision(query: str, results: list[dict]) -> float:
    """Score 0-1: are the retrieved chunks actually relevant to the query?"""
    if not results:
        return 0.0

    relevant_count = 0
    checked = min(len(results), 5)
    for r in results[:checked]:
        prompt = (
            "Is this text relevant to the question? "
            "Answer ONLY 'yes' or 'no'.\n\n"
            f"Question: {query}\n\n"
            f"Text: {r.get('summary', '')[:500]}\n\n"
            "Answer:"
        )
        raw = _query_ollama(prompt).lower().strip()
        if "yes" in raw:
            relevant_count += 1

    return relevant_count / checked


def evaluate_rag(
    query: str, answer: str, context: str, results: list[dict]
) -> dict:
    """Run full RAGAS-style evaluation suite.

    Returns faithfulness, answer_relevancy, context_precision, and
    an overall composite score.
    """
    faithfulness = evaluate_faithfulness(answer, context)
    relevancy = evaluate_relevancy(answer, query)
    context_precision = evaluate_context_precision(query, results)

    overall = (faithfulness + relevancy + context_precision) / 3

    scores = {
        "faithfulness": round(faithfulness, 3),
        "answer_relevancy": round(relevancy, 3),
        "context_precision": round(context_precision, 3),
        "overall": round(overall, 3),
    }
    logger.info(f"RAGAS evaluation: {scores}")
    return scores
