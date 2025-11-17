"""Utilities to configure LLM clients."""
from __future__ import annotations

import os
from dotenv import load_dotenv
from typing import Optional

from openai import OpenAI

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_PROVIDER = "openai"


def _resolve_provider(provider: Optional[str] = None) -> str:
    value = (provider or os.getenv("LLM_PROVIDER") or _DEFAULT_PROVIDER).strip().lower()
    return value


def get_default_model(provider: Optional[str] = None) -> str:
    resolved = _resolve_provider(provider)
    if resolved == "groq":
        return os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905")
    return os.getenv("GPT_MODEL", "gpt-5.1")


def create_chat_client(provider: Optional[str] = None) -> OpenAI:
    # Ensure .env takes precedence over OS env for this process
    try:
        load_dotenv(override=True)
    except Exception:
        pass
    resolved = _resolve_provider(provider)
    if resolved == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        return OpenAI(base_url=_GROQ_BASE_URL, api_key=api_key)

    api_key = os.getenv("GPT_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("GPT_API_KEY or OPENAI_API_KEY is not configured")

    base_url = os.getenv("GPT_API_BASE")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
