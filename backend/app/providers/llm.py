"""Universal LLM caller for caption + hashtag + voice-over script generation.

We expose one async function `chat_completion(creds, messages)` that dispatches
to the right vendor based on `creds.provider`. All vendors are called via
their HTTPS chat-completions endpoint with httpx; no SDKs.

Supported providers:
    - openai (chat.completions)
    - anthropic (v1/messages)
    - gemini (generateContent)
    - groq (OpenAI-compatible)
    - openrouter (OpenAI-compatible)
    - deepseek (OpenAI-compatible)
    - openai_compatible (custom base_url)
"""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas import LLMCreds

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "openai/gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "openai_compatible": "gpt-4o-mini",
}

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openai_compatible": "",  # must be supplied by user
}


class LLMError(RuntimeError):
    pass


async def chat_completion(
    creds: LLMCreds,
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    timeout: float = 60.0,
) -> str:
    """Call the configured provider and return the assistant text."""

    model = creds.model or DEFAULT_MODELS.get(creds.provider) or "gpt-4o-mini"
    base_url = (creds.base_url or DEFAULT_BASE_URLS.get(creds.provider) or "").rstrip("/")

    args = (creds.api_key, base_url, model, system, user, temperature, max_tokens, timeout)
    if creds.provider == "anthropic":
        return await _anthropic(*args)
    if creds.provider == "gemini":
        return await _gemini(*args)

    # Everything else is OpenAI-compatible
    if not base_url:
        raise LLMError(
            f"base_url wajib untuk provider {creds.provider!r}. "
            "Tempelkan endpoint OpenAI-compatible Anda di Settings."
        )
    return await _openai_compatible(*args)


async def _openai_compatible(
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise LLMError(f"LLM provider error {r.status_code}: {r.text[:500]}")
        data = r.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Format respon LLM tidak terduga: {data!r:.500}") from exc


async def _anthropic(
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    url = f"{base_url}/messages"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise LLMError(f"Anthropic error {r.status_code}: {r.text[:500]}")
        data = r.json()
    try:
        parts = data["content"]
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise LLMError(f"Format respon Anthropic tidak terduga: {data!r:.500}") from exc


async def _gemini(
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    url = f"{base_url}/models/{model}:generateContent?key={api_key}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise LLMError(f"Gemini error {r.status_code}: {r.text[:500]}")
        data = r.json()
    try:
        candidates = data["candidates"]
        if not candidates:
            return ""
        parts = candidates[0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Format respon Gemini tidak terduga: {data!r:.500}") from exc
