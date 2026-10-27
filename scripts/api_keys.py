#!/usr/bin/env python3
"""Load image-backend API keys for FigEcho.

Real environment variables always win. Files only fill in what is not already
set (standard dotenv semantics). Candidate files, in order:

  1. <skill root>/.env                       (this skill's own keys)
  2. ~/.claude/image-backends.env            (shared across skills)
  3. ~/.claude/skills/figedit-v2/.env        (reuse an existing figedit setup)

The shared and figedit files let one Labnana key serve every image skill
without copying the secret around. Never commit any of them.
"""
from __future__ import annotations

SCRIPT_INTERFACE = "internal-module"

import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_HOME = Path.home() / ".claude"

CANDIDATES = [
    SKILL_ROOT / ".env",
    CLAUDE_HOME / "image-backends.env",
    CLAUDE_HOME / "skills" / "figedit-v2" / ".env",
]

KNOWN_KEYS = {
    "LISTENHUB_API_KEY",
    "LISTENHUB_BASE_URL",
    "LABNANA_API_KEY",
    "LABNANA_BASE_URL",
    "FIGECHO_GPT_MODELS",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "FIGECHO_IMAGE_BACKEND",
    "FIGECHO_IMAGE_CONFIG",
    "FIGECHO_OPENAI_IMAGE_MODEL",
    "FIGECHO_GEMINI_IMAGE_MODEL",
}


def _load_file(path: Path) -> list[str]:
    loaded: list[str] = []
    if not path.exists():
        return loaded
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return loaded
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def load() -> dict[str, list[str]]:
    """Merge candidate env files into os.environ. Returns {file: [keys]}."""
    result: dict[str, list[str]] = {}
    for path in CANDIDATES:
        keys = _load_file(path)
        if keys:
            result[str(path)] = keys
    return result


if __name__ == "__main__":
    import json

    loaded = load()
    print(
        json.dumps(
            {
                "loaded": loaded,
                "present_now": sorted(k for k in KNOWN_KEYS if os.environ.get(k)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
