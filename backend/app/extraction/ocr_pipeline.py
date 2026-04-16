import easyocr
from PIL import Image
from app.utils.logger import get_logger

logger = get_logger("ocr_pipeline")

# Lazy-loaded global reader
_easyocr_reader = None


def _get_reader() -> easyocr.Reader:
    global _easyocr_reader
    if _easyocr_reader is None:
        logger.info("Loading EasyOCR reader...")
        _easyocr_reader = easyocr.Reader(["en"], gpu=True)
    return _easyocr_reader


def extract_text_easyocr(image_path: str) -> str:
    """Extract text from image using EasyOCR."""
    try:
        reader = _get_reader()
        results = reader.readtext(image_path, detail=0)
        text = " ".join(results).strip()
        logger.info(f"EasyOCR extracted {len(text)} chars from {image_path}")
        return text
    except Exception as e:
        logger.error(f"EasyOCR error for {image_path}: {e}")
        return ""


def extract_text_tesseract(image_path: str) -> str:
    """Extract text from image using Tesseract OCR."""
    try:
        import pytesseract

        image = Image.open(image_path)
        text = pytesseract.image_to_string(image).strip()
        logger.info(f"Tesseract extracted {len(text)} chars from {image_path}")
        return text
    except ImportError:
        logger.warning("pytesseract not installed, skipping Tesseract OCR")
        return ""
    except Exception as e:
        logger.error(f"Tesseract error for {image_path}: {e}")
        return ""


def run_ocr(image_path: str, min_text_length: int = 20) -> tuple[str, str]:
    """
    Run OCR pipeline with smart routing.

    Returns:
        (extracted_text, method): method is 'easyocr', 'tesseract', or 'none'
    """
    # Try EasyOCR first
    text = extract_text_easyocr(image_path)
    if len(text) >= min_text_length:
        return text, "easyocr"

    # Fallback to Tesseract
    text_tess = extract_text_tesseract(image_path)
    if len(text_tess) >= min_text_length:
        return text_tess, "tesseract"

    # Combine whatever we got
    combined = f"{text} {text_tess}".strip()
    if len(combined) >= min_text_length:
        return combined, "combined"

    return combined, "none"
