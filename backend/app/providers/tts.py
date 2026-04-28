"""Universal TTS caller. Returns mp3 bytes."""

from __future__ import annotations

import binascii

import httpx

from app.schemas import TTSCreds

DEFAULT_MODELS: dict[str, str] = {
    "elevenlabs": "eleven_multilingual_v2",
    "openai": "gpt-4o-mini-tts",
    "gemini": "gemini-2.5-flash-preview-tts",
    "minimax": "speech-2.8-hd",
    "openai_compatible": "tts-1",
}

DEFAULT_VOICES: dict[str, str] = {
    "elevenlabs": "21m00Tcm4TlvDq8ikWAM",  # "Rachel"
    "openai": "alloy",
    "gemini": "Kore",
    "minimax": "Indonesian_SweetGirl",
    "openai_compatible": "alloy",
}

DEFAULT_BASE_URLS: dict[str, str] = {
    "elevenlabs": "https://api.elevenlabs.io/v1",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "minimax": "https://api.minimax.io/v1",
    "openai_compatible": "",
}


class TTSError(RuntimeError):
    pass


async def tts(creds: TTSCreds, text: str, *, timeout: float = 90.0) -> bytes:
    """Generate mp3 audio bytes from text."""
    if not text.strip():
        raise TTSError("Teks kosong.")

    model = creds.model or DEFAULT_MODELS.get(creds.provider) or "tts-1"
    voice = creds.voice or DEFAULT_VOICES.get(creds.provider) or "alloy"
    base_url = (creds.base_url or DEFAULT_BASE_URLS.get(creds.provider) or "").rstrip("/")

    if creds.provider == "elevenlabs":
        return await _elevenlabs(creds.api_key, base_url, voice, model, text, timeout)
    if creds.provider == "gemini":
        return await _gemini_tts(creds.api_key, base_url, model, voice, text, timeout)
    if creds.provider == "minimax":
        return await _minimax_tts(creds.api_key, base_url, model, voice, text, timeout)
    # openai + openai_compatible
    if not base_url:
        raise TTSError(
            f"base_url wajib untuk provider {creds.provider!r}. "
            "Tempelkan endpoint OpenAI-compatible Anda di Settings."
        )
    return await _openai_tts(creds.api_key, base_url, model, voice, text, timeout)


async def _openai_tts(
    api_key: str, base_url: str, model: str, voice: str, text: str, timeout: float
) -> bytes:
    url = f"{base_url}/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "voice": voice, "input": text, "response_format": "mp3"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise TTSError(f"OpenAI TTS error {r.status_code}: {r.text[:500]}")
        return r.content


async def _elevenlabs(
    api_key: str, base_url: str, voice_id: str, model: str, text: str, timeout: float
) -> bytes:
    url = f"{base_url}/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise TTSError(f"ElevenLabs error {r.status_code}: {r.text[:500]}")
        return r.content


async def _gemini_tts(
    api_key: str, base_url: str, model: str, voice: str, text: str, timeout: float
) -> bytes:
    """Gemini TTS via generateContent with audio response.

    Gemini returns base64-encoded audio in the JSON response body.
    """
    import base64

    url = f"{base_url}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
            },
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        if r.status_code >= 400:
            raise TTSError(f"Gemini TTS error {r.status_code}: {r.text[:500]}")
        data = r.json()
    try:
        b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TTSError(f"Format respon Gemini TTS tidak terduga: {data!r:.500}") from exc
    return base64.b64decode(b64)


async def _minimax_tts(
    api_key: str, base_url: str, model: str, voice: str, text: str, timeout: float
) -> bytes:
    """MiniMax T2A v2 (https://api.minimax.io/v1/t2a_v2).

    Returns hex-encoded MP3 bytes inside ``data.audio``. We always request
    non-streaming MP3 at 32 kHz / 128 kbps mono so the slideshow composer can
    consume it directly.
    """
    url = f"{base_url}/t2a_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "language_boost": "Indonesian",
        "voice_setting": {
            "voice_id": voice,
            "speed": 1,
            "vol": 1,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise TTSError(f"MiniMax TTS error {r.status_code}: {r.text[:500]}")
        data = r.json()
    base = data.get("base_resp") or {}
    if base.get("status_code") not in (0, None):
        raise TTSError(
            f"MiniMax TTS gagal ({base.get('status_code')}): {base.get('status_msg')}"
        )
    audio_hex = (data.get("data") or {}).get("audio") or ""
    if not audio_hex:
        raise TTSError(f"Format respon MiniMax TTS tidak terduga: {data!r:.500}")
    try:
        return binascii.unhexlify(audio_hex)
    except (binascii.Error, ValueError) as exc:
        raise TTSError(f"Audio MiniMax bukan hex valid: {exc!s}") from exc
