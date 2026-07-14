"""
Cleans raw extracted text before it's sent to the LLM:
- Collapses whitespace/newlines
- Strips common boilerplate (cookie notices, "subscribe now", share prompts)
- Removes very short junk lines (nav labels, etc.)
"""
import re

BOILERPLATE_PATTERNS = [
    r"^\s*(cookie|accept cookies|we use cookies).{0,80}$",
    r"^\s*(subscribe|sign up)( now| today)?( to (our|the) newsletter)?\s*$",
    r"^\s*(share this|follow us on|read more|advertisement)\s*$",
    r"^\s*©\s?\d{4}.*$",
    r"^\s*all rights reserved\.?\s*$",
]

_COMPILED_BOILERPLATE = [re.compile(p, re.IGNORECASE) for p in BOILERPLATE_PATTERNS]

MIN_LINE_LENGTH = 3


def clean_text(raw_text: str) -> str:
    if not raw_text:
        return ""

    # Normalize whitespace
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    lines = [ln.strip() for ln in text.split("\n")]

    cleaned_lines = []
    for line in lines:
        if not line or len(line) < MIN_LINE_LENGTH:
            continue
        if any(pattern.match(line) for pattern in _COMPILED_BOILERPLATE):
            continue
        cleaned_lines.append(line)

    # Collapse 3+ blank lines into a single paragraph break
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
