import re
from app.utils.logger import get_logger

logger = get_logger("chunker")


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, respecting paragraph structure.

    Strategy:
    - Paragraph breaks (double newline) are hard boundaries.
    - Within paragraphs, split on sentence-ending punctuation followed
      by whitespace and an uppercase letter or digit.
    - Numbered list items and bullet lines each become their own sentence.
    """
    # Normalise excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    sentences: list[str] = []
    # Sentence boundary: . ! ? followed by space + capital/digit
    sent_re = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"])")

    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue

        # Detect list-style paragraphs (lines starting with bullet/number)
        lines = para.split("\n")
        if len(lines) > 1 and re.match(r"^\s*[-•*\d]+[\.\)]\s", lines[0]):
            # Each line is its own "sentence"
            for line in lines:
                line = line.strip()
                if line:
                    sentences.append(line)
        else:
            # Split at sentence boundaries
            parts = sent_re.split(para)
            for part in parts:
                part = part.strip()
                if part:
                    sentences.append(part)

    return sentences


def chunk_text(
    text: str, chunk_size: int = 300, overlap: int = 80
) -> list[str]:
    """Split text into overlapping chunks that respect sentence boundaries.

    Improvements over the old word-based approach:
    - Never cuts mid-sentence.
    - Sentence-level sliding window: overlap is measured in words but always
      includes whole sentences, so chunks share coherent context.
    - Short documents (under chunk_size words) returned as a single chunk.
    """
    if not text or not text.strip():
        return []

    sentences = _split_into_sentences(text)

    if not sentences:
        # Fallback: plain word-based split (very rare)
        words = text.split()
        if len(words) <= chunk_size:
            return [text.strip()]
        chunks, start = [], 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunks.append(" ".join(words[start:end]))
            if end >= len(words):
                break
            start = end - overlap
        return chunks

    word_counts = [len(s.split()) for s in sentences]
    total_words = sum(word_counts)

    if total_words <= chunk_size:
        return [" ".join(sentences)]

    chunks: list[str] = []
    start_idx = 0

    while start_idx < len(sentences):
        # Accumulate sentences until chunk_size is reached
        end_idx = start_idx
        current_words = 0

        while end_idx < len(sentences):
            next_words = word_counts[end_idx]
            # Allow a single oversized sentence to form its own chunk
            if current_words + next_words > chunk_size and end_idx > start_idx:
                break
            current_words += next_words
            end_idx += 1

        chunk = " ".join(sentences[start_idx:end_idx]).strip()
        if chunk:
            chunks.append(chunk)

        if end_idx >= len(sentences):
            break

        # Step back to find overlap start (word-count aligned to sentence boundaries)
        overlap_words = 0
        new_start = end_idx  # default: no overlap
        for i in range(end_idx - 1, start_idx - 1, -1):
            overlap_words += word_counts[i]
            if overlap_words >= overlap:
                new_start = i
                break

        # Guarantee forward progress
        start_idx = max(new_start, start_idx + 1)

    logger.info(
        f"Sentence-aware chunking: {total_words} words → "
        f"{len(chunks)} chunks (target={chunk_size}w, overlap={overlap}w)"
    )
    return chunks
