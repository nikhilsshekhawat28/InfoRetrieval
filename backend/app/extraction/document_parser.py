from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger("document_parser")


def extract_from_pdf(file_path: str) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        full_text = "\n\n".join(pages)
        logger.info(f"PDF extracted {len(full_text)} chars from {file_path}")
        return full_text
    except Exception as e:
        logger.error(f"PDF extraction error for {file_path}: {e}")
        return ""


def extract_from_docx(file_path: str) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document

        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        logger.info(f"DOCX extracted {len(full_text)} chars from {file_path}")
        return full_text
    except Exception as e:
        logger.error(f"DOCX extraction error for {file_path}: {e}")
        return ""


def extract_from_text(file_path: str) -> str:
    """Read plain text file."""
    try:
        text = Path(file_path).read_text(encoding="utf-8")
        logger.info(f"Text file read {len(text)} chars from {file_path}")
        return text.strip()
    except Exception as e:
        logger.error(f"Text file error for {file_path}: {e}")
        return ""


def parse_document(file_path: str) -> str:
    """Route document to appropriate parser based on extension."""
    ext = Path(file_path).suffix.lower()
    parsers = {
        ".pdf": extract_from_pdf,
        ".docx": extract_from_docx,
        ".doc": extract_from_docx,
        ".txt": extract_from_text,
        ".md": extract_from_text,
        ".csv": extract_from_text,
        ".json": extract_from_text,
    }
    parser = parsers.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported document format: {ext}")
    text = parser(file_path)
    if not text:
        raise ValueError(f"No text extracted from {file_path}")
    return text
