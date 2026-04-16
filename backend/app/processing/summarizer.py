from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from app.config import settings, DEVICE
from app.utils.logger import get_logger

logger = get_logger("summarizer")

_model = None
_tokenizer = None


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return

    model_name = settings.summarizer_model
    logger.info(f"Loading summarization model: {model_name}")

    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    device = DEVICE if DEVICE != "mps" else "cpu"
    _model = _model.to(device)
    _model.eval()
    logger.info(f"Summarizer loaded on {device}")


def smart_truncate(text: str, max_chars: int = 2000) -> str:
    """Truncate text at sentence boundary."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Find last sentence boundary
    for sep in [". ", "! ", "? ", "\n"]:
        idx = truncated.rfind(sep)
        if idx > max_chars * 0.5:
            return truncated[: idx + 1].strip()
    return truncated.strip()


def summarize(text: str, max_length: int = 200, min_length: int = 30) -> str:
    """Summarize text using T5 model."""
    _load_model()

    if len(text.strip()) < 50:
        return text.strip()

    truncated = smart_truncate(text, max_chars=2000)

    try:
        prompt = f"summarize: {truncated}"
        device = DEVICE if DEVICE != "mps" else "cpu"
        inputs = _tokenizer(
            prompt, return_tensors="pt", max_length=512, truncation=True
        ).to(device)

        with torch.no_grad():
            output_ids = _model.generate(
                **inputs,
                max_length=max_length,
                min_length=min_length,
                num_beams=4,
                repetition_penalty=1.2,
                no_repeat_ngram_size=3,
            )

        summary = _tokenizer.decode(output_ids[0], skip_special_tokens=True)
        logger.info(f"Summarized {len(text)} chars -> {len(summary)} chars")
        return summary.strip()
    except Exception as e:
        logger.error(f"Summarization error: {e}")
        return smart_truncate(text, max_chars=200)
