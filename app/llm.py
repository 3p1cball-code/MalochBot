"""LLM-Backend-Fassade: leitet Analysen je nach Einstellung an opencode oder
Claude Code weiter.

Alle Engines sprechen nur noch mit `llm.*`. Welches Backend genutzt wird,
entscheidet die Einstellung `llm_backend`; das jeweilige Modell kommt aus
`model` (opencode) bzw. `claude_model` (Claude Code). Die JSON-Extraktion ist
backend-unabhaengig und wird direkt aus `llm_common` weitergereicht.
"""

from . import config
from . import opencode_adapter
from . import claude_adapter
from .llm_common import extract_json  # noqa: F401 (backend-unabhaengig)

BACKENDS = ("opencode", "claude")

_LABELS = {"opencode": "opencode", "claude": "Claude Code"}


def backend() -> str:
    from . import db
    value = (db.get_setting("llm_backend", "opencode") or "opencode").strip().lower()
    return value if value in BACKENDS else "opencode"


def backend_label() -> str:
    return _LABELS.get(backend(), "opencode")


def _adapter():
    return claude_adapter if backend() == "claude" else opencode_adapter


def available() -> bool:
    return _adapter().available()


def list_models():
    return _adapter().list_models()


def active_model() -> str:
    """Das fuer das aktive Backend gespeicherte Modell (mit sinnvollem Standard)."""
    from . import db
    if backend() == "claude":
        return (db.get_setting("claude_model", claude_adapter.DEFAULT_MODEL)
                or claude_adapter.DEFAULT_MODEL)
    return db.get_setting("model", config.DEFAULT_MODEL) or config.DEFAULT_MODEL


def run(prompt, model: str = "", cwd: str = "", attach=None, run_id=None, timeout: int = 3600):
    model = model or active_model()
    return _adapter().run(prompt, model=model, cwd=cwd, attach=attach,
                          run_id=run_id, timeout=timeout)


def clean_text(text: str) -> str:
    return _adapter().clean_text(text)
