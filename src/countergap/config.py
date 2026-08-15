"""Tiny .env loader and environment access (stdlib only, no python-dotenv).

Loads KEY=VALUE lines from a `.env` file next to the repository root or in
the current working directory. Values already present in the environment take
precedence so CI/shell secrets are never shadowed.
"""

from __future__ import annotations

import os
from pathlib import Path


def _default_env_path() -> Path | None:
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(path: str | Path | None = None) -> Path | None:
    """Load `KEY=VALUE` pairs from a .env file if present. Returns the path used."""
    env_path = Path(path) if path is not None else _default_env_path()
    if env_path is None or not env_path.is_file():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


def get_env(key: str, default: str | None = None) -> str | None:
    """Return an environment variable, loading .env first if needed."""
    load_dotenv()
    return os.environ.get(key, default)
