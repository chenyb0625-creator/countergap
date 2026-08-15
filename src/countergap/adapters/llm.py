"""Model integrations live behind a small interface.

AGENTS.md dependency policy: base repository must not require paid APIs, so
the LLM adapter is optional and only imported when a run explicitly asks for
it. The DeepSeek client uses only the Python standard library.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from countergap.config import get_env

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/chat/completions"


class LLMError(RuntimeError):
    """Raised when a model call fails in a way the caller must handle."""


class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str: ...


class DeepSeekClient:
    """OpenAI-compatible chat client for DeepSeek, stdlib only.

    Reads the API key from the ``DEEPSEEK_API_KEY`` environment variable
    (which the :mod:`countergap.config` loader populates from a gitignored
    ``.env`` file). The key is never logged or written into traces.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.api_key = api_key or get_env("DEEPSEEK_API_KEY", "") or ""
        self.model = model or get_env("DEEPSEEK_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
        self.base_url = base_url or get_env("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
        self.timeout = timeout
        if not self.api_key:
            raise LLMError(
                "DEEPSEEK_API_KEY is not set. Create a `.env` file from `.env.example` "
                "or export the variable."
            )

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise LLMError(f"DeepSeek HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise LLMError(f"DeepSeek connection error: {error.reason}") from error
        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError(f"Unexpected DeepSeek response shape: {str(body)[:300]}") from error


def extract_json_object(text: str) -> dict:
    """Best-effort parse of a JSON object from an LLM reply.

    Handles replies wrapped in markdown fences or with surrounding prose.
    Raises :class:`LLMError` when no object can be recovered.
    """
    if not isinstance(text, str) or not text.strip():
        raise LLMError("Empty model reply; expected a JSON object.")
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError(f"Model reply contains no JSON object: {text[:200]!r}")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as error:
        raise LLMError(f"Model reply is not valid JSON: {text[:200]!r}") from error
    if not isinstance(parsed, dict):
        raise LLMError(f"Model reply is not a JSON object: {text[:200]!r}")
    return parsed
