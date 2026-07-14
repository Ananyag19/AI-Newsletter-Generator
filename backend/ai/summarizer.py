"""
Summarizes cleaned/chunked content and extracts key bullet points per source,
so the newsletter writer step works from concise material instead of raw text.
"""
from ai.llm_client import generate
from models.schemas import ExtractedContent
from processing.chunker import chunk_text
from processing.text_cleaner import clean_text

SUMMARIZE_SYSTEM_PROMPT = """You are a precise news summarizer for a newsletter production pipeline.
Given a chunk of article or notes text, extract the most newsletter-worthy information.
Rules:
- Output 3 to 6 concise bullet points capturing the key facts, numbers, and takeaways.
- Do not editorialize or add information that isn't in the text.
- Do not include boilerplate like "subscribe" or "click here".
- Each bullet should be a single self-contained sentence.
- Output ONLY the bullet points, one per line, starting each with "- ".
"""


def _summarize_chunk(chunk: str) -> list[str]:
    user_prompt = f"Text to summarize:\n\n{chunk}"
    raw = generate(SUMMARIZE_SYSTEM_PROMPT, user_prompt, temperature=0.3)
    bullets = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line.startswith("-"):
            bullets.append(line[1:].strip())
    return [b for b in bullets if b]


def summarize_source(content: ExtractedContent) -> list[str]:
    """Clean, chunk, and summarize a single extracted content item into
    a flat list of key-point bullets."""
    if content.error or not content.text.strip():
        return []

    cleaned = clean_text(content.text)
    chunks = chunk_text(cleaned)

    all_bullets: list[str] = []
    for chunk in chunks:
        all_bullets.extend(_summarize_chunk(chunk))

    return all_bullets


def summarize_all(contents: list[ExtractedContent]) -> dict[str, list[str]]:
    """Returns a mapping of source identifier -> list of key-point bullets."""
    results: dict[str, list[str]] = {}
    for content in contents:
        results[content.source] = summarize_source(content)
    return results
