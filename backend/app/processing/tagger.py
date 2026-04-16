import re
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from app.config import settings, DEVICE
from app.utils.logger import get_logger

logger = get_logger("tagger")

_model = None
_tokenizer = None


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return

    model_name = settings.summarizer_model
    logger.info(f"Loading tagger model: {model_name}")
    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    device = DEVICE if DEVICE != "mps" else "cpu"
    _model = _model.to(device)
    _model.eval()
    logger.info("Tagger model loaded")


def generate_tags(text: str, max_tags: int = 5) -> list[str]:
    """Generate descriptive tags from text content using T5."""
    _load_model()
    try:
        prompt = (
            f"Generate {max_tags} short topic tags for this text, "
            f"separated by commas: {text[:500]}"
        )
        device = DEVICE if DEVICE != "mps" else "cpu"
        inputs = _tokenizer(
            prompt, return_tensors="pt", max_length=512, truncation=True
        ).to(device)

        with torch.no_grad():
            output_ids = _model.generate(**inputs, max_length=60, num_beams=2)

        raw = _tokenizer.decode(output_ids[0], skip_special_tokens=True)
        # Parse comma-separated tags and clean them
        tags = [t.strip().lower() for t in re.split(r"[,;]", raw) if t.strip()]
        tags = [t for t in tags if len(t) > 1 and len(t) < 50][:max_tags]
        logger.info(f"Generated tags: {tags}")
        return tags
    except Exception as e:
        logger.error(f"Tag generation error: {e}")
        return []
