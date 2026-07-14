"""
Runtime-configurable settings that an admin can change through the API
without restarting the server.

Only ONE thing lives here today: which AI provider is currently active.
It's persisted to a small JSON file so the choice survives a server restart,
instead of always falling back to whatever AI_PROVIDER is in .env.

This is intentionally simple (a JSON file + a lock), not a database — fine
for a single-instance deployment. If you ever run multiple backend
instances, swap this for a shared store (Redis, a DB row, etc.).
"""
import json
import logging
import threading
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).parent / "data" / "runtime_state.json"
_lock = threading.Lock()

VALID_PROVIDERS = {"groq", "gemini", "qwen", "grok_drive"}


def _read_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read runtime_state.json (%s); using defaults.", e)
    return {}


def _write_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def get_active_provider() -> str:
    """Returns the currently active provider: an admin's saved override if
    one exists, otherwise the AI_PROVIDER default from .env."""
    with _lock:
        state = _read_state()
    return state.get("active_provider", settings.AI_PROVIDER)


def set_active_provider(provider: str) -> None:
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Valid options: {sorted(VALID_PROVIDERS)}"
        )
    with _lock:
        state = _read_state()
        state["active_provider"] = provider
        _write_state(state)
    logger.info("Active AI provider changed to '%s'", provider)
