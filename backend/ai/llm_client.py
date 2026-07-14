"""
Thin unified wrapper around all supported LLM providers so the rest of the
app can call `generate(system_prompt, user_prompt)` without caring which
one is active.

Providers:
- groq        OpenAI-compatible /chat/completions endpoint
- gemini      Gemini's own generateContent endpoint
- qwen        DashScope's OpenAI-compatible /chat/completions endpoint
- grok_drive  No direct API call. Writes a task file to a shared Google
              Drive folder, waits for a scheduled Grok Task (grok.com/tasks,
              connected to Drive) to process it and write a result file
              back, then reads that file. See integrations/google_drive.py.

Which provider is active is looked up via runtime_settings.get_active_provider()
on every call — this is what lets an admin switch providers through the API
without restarting the server (see main.py's /admin/provider routes).
"""
import json
import logging
import time
import uuid

import requests

import runtime_settings
from config import settings
from integrations import google_drive

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


def _call_groq(system_prompt: str, user_prompt: str, temperature: float) -> str:
    if not settings.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set. Add it to your .env file.")

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    resp = requests.post(
        GROQ_URL, headers=headers, json=payload, timeout=settings.LLM_REQUEST_TIMEOUT
    )
    if resp.status_code != 200:
        raise LLMError(f"Groq API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected Groq response shape: {data}") from e


def _call_gemini(system_prompt: str, user_prompt: str, temperature: float) -> str:
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set. Add it to your .env file.")

    url = GEMINI_URL_TMPL.format(model=settings.GEMINI_MODEL, key=settings.GEMINI_API_KEY)
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    resp = requests.post(url, json=payload, timeout=settings.LLM_REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise LLMError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected Gemini response shape: {data}") from e


def _call_qwen(system_prompt: str, user_prompt: str, temperature: float) -> str:
    if not settings.QWEN_API_KEY:
        raise LLMError("QWEN_API_KEY is not set. Add it to your .env file.")

    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    resp = requests.post(
        settings.QWEN_BASE_URL, headers=headers, json=payload, timeout=settings.LLM_REQUEST_TIMEOUT
    )
    if resp.status_code != 200:
        raise LLMError(f"Qwen API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected Qwen response shape: {data}") from e


def _call_grok_drive(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """Hands the task off to a scheduled Grok Task via a shared Drive folder,
    then blocks (polling) until Grok writes a result file back or we time out.

    This is much slower than a direct API call — Grok Tasks run on their own
    schedule, not instantly on file arrival — so callers should expect this
    to take anywhere from ~1 to GROK_DRIVE_MAX_WAIT_SECONDS.
    """
    task_id = uuid.uuid4().hex[:10]
    in_filename = f"inbox_task_{task_id}.txt"
    out_filename = f"outbox_task_{task_id}.md"

    instructions = (
        "=== TASK INSTRUCTIONS FOR GROK ===\n"
        f"{system_prompt.strip()}\n\n"
        "=== INPUT ===\n"
        f"{user_prompt.strip()}\n\n"
        "=== OUTPUT REQUIREMENT ===\n"
        f"Save your complete response as a new file named exactly "
        f"`{out_filename}` in this same Drive folder. The file should "
        "contain ONLY the requested content (no preamble, no commentary "
        "about what you did) so it can be parsed programmatically."
    )

    try:
        google_drive.upload_text_file(in_filename, instructions)
    except google_drive.DriveError as e:
        raise LLMError(f"Could not hand task off to Drive: {e}") from e

    logger.info("Uploaded %s to Drive; waiting for Grok to produce %s", in_filename, out_filename)

    waited = 0
    poll_interval = settings.GROK_DRIVE_POLL_INTERVAL_SECONDS
    max_wait = settings.GROK_DRIVE_MAX_WAIT_SECONDS

    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval
        try:
            file_id = google_drive.find_file_by_name(out_filename)
        except google_drive.DriveError as e:
            raise LLMError(f"Error while polling Drive for Grok's result: {e}") from e

        if file_id:
            try:
                return google_drive.download_file_text(file_id)
            except google_drive.DriveError as e:
                raise LLMError(f"Found {out_filename} but couldn't download it: {e}") from e

    raise LLMError(
        f"Timed out after {max_wait}s waiting for Grok to process {in_filename}. "
        "Check that the scheduled Grok Task is active and pointed at the "
        "correct Drive folder."
    )


def generate(system_prompt: str, user_prompt: str, temperature: float = 0.5) -> str:
    """Call the currently active LLM provider and return its raw text response."""
    provider = runtime_settings.get_active_provider()
    if provider == "groq":
        return _call_groq(system_prompt, user_prompt, temperature)
    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, temperature)
    if provider == "qwen":
        return _call_qwen(system_prompt, user_prompt, temperature)
    if provider == "grok_drive":
        return _call_grok_drive(system_prompt, user_prompt, temperature)
    raise LLMError(
        f"Unknown active provider '{provider}'. Valid options: "
        f"{sorted(runtime_settings.VALID_PROVIDERS)}"
    )


def generate_json(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> dict:
    """Call the LLM expecting a strict JSON object back, with basic cleanup
    of markdown code fences that models sometimes add despite instructions."""
    raw = generate(system_prompt, user_prompt, temperature)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        # Strip a leading language tag like "json\n"
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", e, raw)
        raise LLMError(f"Model did not return valid JSON: {e}") from e
