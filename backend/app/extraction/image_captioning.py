import torch
from PIL import Image
from pathlib import Path
from transformers import BlipProcessor, BlipForConditionalGeneration
from peft import PeftModel
from app.config import settings, DEVICE
from app.utils.logger import get_logger

logger = get_logger("image_captioning")

_processor = None
_model = None


def _load_model():
    global _processor, _model
    if _model is not None:
        return

    logger.info("Loading BLIP image captioning model...")
    base_model_name = "Salesforce/blip-image-captioning-base"
    _processor = BlipProcessor.from_pretrained(base_model_name)

    finetuned_path = Path(settings.blip_model_path)
    if finetuned_path.exists() and (finetuned_path / "adapter_config.json").exists():
        logger.info(f"Loading fine-tuned LoRA adapter from {finetuned_path}")
        base_model = BlipForConditionalGeneration.from_pretrained(base_model_name)
        _model = PeftModel.from_pretrained(base_model, str(finetuned_path))
        _model.eval()
    else:
        logger.info("No fine-tuned model found, using base BLIP model")
        _model = BlipForConditionalGeneration.from_pretrained(base_model_name)
        _model.eval()

    device = "cpu" if DEVICE == "mps" else DEVICE
    _model = _model.to(device)
    logger.info(f"BLIP model loaded on {device}")


def generate_caption(image_path: str) -> str:
    """Generate a descriptive caption for an image using BLIP + LoRA."""
    _load_model()
    try:
        image = Image.open(image_path).convert("RGB")
        device = "cpu" if DEVICE == "mps" else DEVICE
        inputs = _processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            output_ids = _model.generate(**inputs, max_new_tokens=100)

        caption = _processor.decode(output_ids[0], skip_special_tokens=True)
        logger.info(f"Caption for {image_path}: {caption}")
        return caption.strip()
    except Exception as e:
        logger.error(f"Captioning error for {image_path}: {e}")
        return ""
