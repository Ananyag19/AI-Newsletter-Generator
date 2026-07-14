"""
Splits cleaned text into overlapping word-based chunks so long articles can
be summarized within an LLM's context/output limits.
"""
from config import settings


def chunk_text(
    text: str,
    max_words: int | None = None,
    overlap_words: int | None = None,
) -> list[str]:
    """Split `text` into chunks of at most `max_words`, with `overlap_words`
    of overlap between consecutive chunks to preserve context continuity."""
    max_words = max_words or settings.CHUNK_MAX_WORDS
    overlap_words = overlap_words or settings.CHUNK_OVERLAP_WORDS

    words = text.split()
    if not words:
        return []

    if len(words) <= max_words:
        return [text]

    chunks = []
    start = 0
    step = max(max_words - overlap_words, 1)

    while start < len(words):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += step

    return chunks
