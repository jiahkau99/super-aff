"""Tests for the /api/util router used by the Tauri desktop frontend."""

from __future__ import annotations

import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import util as util_module


def test_healthz_under_api_prefix():
    client = TestClient(app)
    r = client.get("/api/util/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_healthz_still_works():
    """Root /healthz is what the Rust sidecar uses for early diagnostics."""

    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def _patch_async_client(monkeypatch, handler):
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(util_module.httpx, "AsyncClient", factory)


def test_fetch_image_returns_base64(monkeypatch):
    raw = b"\x89PNG\r\n\x1a\nfake png body"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://example.com/")
        return httpx.Response(200, content=raw, headers={"content-type": "image/png"})

    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://example.com/foo.png"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["image_b64"] == base64.b64encode(raw).decode("ascii")
    assert body["content_type"] == "image/png"


def test_fetch_image_rejects_oversized_payload(monkeypatch):
    big = b"\x00" * (13 * 1024 * 1024)  # > 12 MB cap

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=big, headers={"content-type": "image/png"})

    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://example.com/big.png"},
    )
    assert r.status_code == 413


def test_fetch_image_propagates_upstream_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://example.com/missing.png"},
    )
    assert r.status_code == 502


def test_fetch_image_validates_input_url():
    client = TestClient(app)
    r = client.post("/api/util/fetch-image", json={"url": "not-a-url"})
    assert r.status_code == 422


@pytest.mark.parametrize("path", ["/api/util/fetch-image"])
def test_fetch_image_requires_post(path):
    client = TestClient(app)
    assert client.get(path).status_code == 405
