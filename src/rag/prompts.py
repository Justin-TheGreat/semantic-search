"""Versioned prompt registry.

Prompts live as plain-text files in src/rag/prompts/ named <name>_<version>.txt.
ACTIVE pins which version serves traffic; changing a prompt means adding a new
file and flipping ACTIVE — old versions stay reviewable and revertable.
"""
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


def _load() -> dict[str, dict[str, str]]:
    prompts: dict[str, dict[str, str]] = {}
    for f in sorted(PROMPT_DIR.glob("*_v*.txt")):
        name, _, version = f.stem.rpartition("_")
        prompts.setdefault(name, {})[version] = f.read_text(encoding="utf-8")
    return prompts


PROMPTS = _load()

ACTIVE = {
    "grade": "v1",
    "generate": "v2",
    "verify": "v1",
    "rewrite": "v1",
}


def render(name: str, **kwargs) -> tuple[str, str]:
    """Render the active version of a prompt. Returns (text, version)."""
    version = ACTIVE[name]
    return PROMPTS[name][version].format(**kwargs), version
