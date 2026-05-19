"""LLM abstraction — OpenAI-compatible endpoint, configured via env vars.

All LLM calls in this project go through this module.
No other file may import `openai` or any provider SDK directly.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_REQUIRED = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]


class LLMError(RuntimeError):
    """Raised for any LLM API failure — wraps provider-specific errors."""


def _client() -> OpenAI:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your LLM provider settings."
        )
    return OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
    )


def chat(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    """Send a chat-format request. Returns the assistant's response text."""
    model = os.environ.get("LLM_MODEL", "")
    if not model:
        raise EnvironmentError("LLM_MODEL is not set.")
    try:
        client = _client()
        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except EnvironmentError:
        raise
    except Exception as e:
        raise LLMError(str(e)) from e


def estimate_tokens(messages: List[Dict[str, str]]) -> int:
    """Rough token estimate: word count × 1.3."""
    total_words = sum(
        len(m.get("content", "").split()) for m in messages
    )
    return int(total_words * 1.3)
