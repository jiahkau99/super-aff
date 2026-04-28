"""Unit tests for MiniMax TTS adapter (binascii hex decode + error mapping)."""

from __future__ import annotations

import asyncio
import binascii

import httpx
import pytest

from app.providers import tts as tts_module
from app.providers.tts import TTSError, tts
from app.schemas import TTSCreds


def _patch_async_client(monkeypatch, handler):
    """Replace httpx.AsyncClient with one backed by httpx.MockTransport(handler)."""

    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", factory)


def test_minimax_tts_decodes_hex_audio(monkeypatch):
    fake_mp3 = b"\xff\xfb\x90\x00fake mp3 payload"
    fake_hex = binascii.hexlify(fake_mp3).decode()
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization", "")
        seen["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "data": {"audio": fake_hex, "status": 2},
                "extra_info": {"audio_length": 1234},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
        )

    _patch_async_client(monkeypatch, handler)
    creds = TTSCreds(provider="minimax", api_key="sk-test")
    out = asyncio.run(tts(creds, "halo"))
    assert out == fake_mp3
    assert seen["url"].endswith("/t2a_v2")
    assert seen["auth"].startswith("Bearer ")
    assert b"speech-2.8-hd" in seen["body"]
    assert b"Indonesian_SweetGirl" in seen["body"]


def test_minimax_tts_propagates_status_msg(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "base_resp": {
                    "status_code": 2061,
                    "status_msg": "your current token plan not support model, X",
                }
            },
        )

    _patch_async_client(monkeypatch, handler)
    creds = TTSCreds(provider="minimax", api_key="sk-test", model="X")
    with pytest.raises(TTSError, match="2061"):
        asyncio.run(tts(creds, "halo"))


def test_minimax_tts_propagates_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    _patch_async_client(monkeypatch, handler)
    creds = TTSCreds(provider="minimax", api_key="bad-key")
    with pytest.raises(TTSError, match="401"):
        asyncio.run(tts(creds, "halo"))
