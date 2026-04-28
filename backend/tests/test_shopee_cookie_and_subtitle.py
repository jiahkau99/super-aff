"""Tests for: Shopee cookie passthrough + Settings test endpoints + subtitle SRT.

These are the new features bundled with the cookie-injection / Test-buttons /
subtitle-burn-in PR. They sit at the seams between layers so we mock the
upstream HTTP calls and assert request shape rather than running real ffmpeg
/ Shopee / OpenAI.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.compose import slideshow as slideshow_mod
from app.main import app
from app.routers import shopee as shopee_router
from app.routers import util as util_module
from app.shopee import scraper as scraper_mod


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _patch_async_client(monkeypatch, module: Any, handler) -> None:
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


# ---------------------------------------------------------------------------
# Cookie passthrough
# ---------------------------------------------------------------------------


def test_scrape_request_passes_cookie_header_to_shopee(monkeypatch, client):
    """When the frontend supplies a cookie, the scraper sends it verbatim."""

    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie")
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "error": None,
                "data": {
                    "name": "Sample Product",
                    "description": "desc",
                    "price_min": 1000_000_00,  # 10 IDR after /100000
                    "images": ["abc123"],
                    "item_rating": {"rating_star": 4.7},
                    "historical_sold": 42,
                },
            },
        )

    _patch_async_client(monkeypatch, scraper_mod, handler)

    r = client.post(
        "/api/shopee/scrape",
        json={
            "url": "https://shopee.co.id/product/15/100",
            "cookie": "SPC_EC=abc; SPC_F=def",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["product"]["title"] == "Sample Product"
    assert seen["cookie"] == "SPC_EC=abc; SPC_F=def"
    # Sanity: the request actually went to the Shopee item API.
    assert "shopee.co.id/api/v4/item/get" in seen["url"]


def test_scrape_without_cookie_omits_header(monkeypatch, client):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie")
        return httpx.Response(
            200,
            json={
                "error": None,
                "data": {"name": "X", "description": "", "price_min": 0, "images": []},
            },
        )

    _patch_async_client(monkeypatch, scraper_mod, handler)
    r = client.post(
        "/api/shopee/scrape",
        json={"url": "https://shopee.co.id/product/1/2"},
    )
    assert r.status_code == 200, r.text
    # Empty / missing cookie -> no Cookie header at all (httpx returns None).
    assert seen["cookie"] in (None, "")


def test_scrape_blank_cookie_treated_as_missing(monkeypatch, client):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie")
        return httpx.Response(
            200,
            json={
                "error": None,
                "data": {"name": "X", "description": "", "price_min": 0, "images": []},
            },
        )

    _patch_async_client(monkeypatch, scraper_mod, handler)
    r = client.post(
        "/api/shopee/scrape",
        json={"url": "https://shopee.co.id/product/1/2", "cookie": "   "},
    )
    assert r.status_code == 200
    assert seen["cookie"] in (None, "")


def test_scrape_response_surfaces_anti_bot_403(monkeypatch, client):
    """Even with a cookie, Shopee can still 403 us — make sure we don't crash."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="blocked")

    _patch_async_client(monkeypatch, scraper_mod, handler)
    r = client.post(
        "/api/shopee/scrape",
        json={"url": "https://shopee.co.id/product/1/2", "cookie": "SPC_EC=expired"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert "anti-bot" in (body["error"] or "")


def test_batch_plan_passes_cookie_to_each_row(monkeypatch, client):
    seen: list[str | None] = []

    async def fake_scrape(url: str, *, cookie: str | None = None):
        seen.append(cookie)
        from app.schemas import ShopeeProduct

        return ShopeeProduct(title=f"T-{url[-3:]}", description="", price=100, images=[])

    monkeypatch.setattr(shopee_router, "scrape_shopee_product", fake_scrape)
    # The batch router imports scrape_shopee_product separately.
    from app.routers import batch as batch_router

    monkeypatch.setattr(batch_router, "scrape_shopee_product", fake_scrape)

    r = client.post(
        "/api/batch/plan",
        json={
            "rows": [
                {"url": "https://shopee.co.id/product/1/100", "judul": "", "deskripsi": ""},
                {"url": "https://shopee.co.id/product/1/200", "judul": "", "deskripsi": ""},
            ],
            "cookie": "SPC_EC=batch",
        },
    )
    assert r.status_code == 200, r.text
    assert seen == ["SPC_EC=batch", "SPC_EC=batch"]


# ---------------------------------------------------------------------------
# Settings "Test" endpoints
# ---------------------------------------------------------------------------


def test_test_llm_returns_ok_on_success(monkeypatch, client):
    """The Settings page's "Test koneksi" button hits /api/util/test-llm."""

    async def fake_chat_completion(*_args, **_kwargs):
        return "OK from probe"

    monkeypatch.setattr(util_module.llm_provider, "chat_completion", fake_chat_completion)

    r = client.post(
        "/api/util/test-llm",
        json={
            "creds": {
                "provider": "openai",
                "api_key": "sk-test",
                "model": "gpt-4o-mini",
            }
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "OK from probe" in body["message"]


def test_test_llm_returns_not_ok_on_provider_error(monkeypatch, client):
    async def boom(*_args, **_kwargs):
        raise util_module.llm_provider.LLMError("bad key")

    monkeypatch.setattr(util_module.llm_provider, "chat_completion", boom)
    r = client.post(
        "/api/util/test-llm",
        json={"creds": {"provider": "openai", "api_key": "sk-test"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "bad key" in body["message"]


def test_test_tts_validates_audio_size(monkeypatch, client):
    """TTS providers that 'succeed' but return a tiny error body should fail."""

    async def short_audio(*_args, **_kwargs):
        return b"too small"

    monkeypatch.setattr(util_module.tts_provider, "tts", short_audio)
    r = client.post(
        "/api/util/test-tts",
        json={"creds": {"provider": "openai", "api_key": "sk-test"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "kemungkinan respon error" in body["message"]


def test_test_tts_ok_for_full_audio(monkeypatch, client):
    async def big_audio(*_args, **_kwargs):
        return b"\x00" * 5000

    monkeypatch.setattr(util_module.tts_provider, "tts", big_audio)
    r = client.post(
        "/api/util/test-tts",
        json={"creds": {"provider": "openai", "api_key": "sk-test"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "5000 bytes" in body["message"]


def test_test_shopee_uses_cookie(monkeypatch, client):
    seen: dict[str, Any] = {}

    async def fake_scrape(url: str, *, cookie: str | None = None):
        seen["url"] = url
        seen["cookie"] = cookie
        from app.schemas import ShopeeProduct

        return ShopeeProduct(title="Test Item", description="", price=None, images=[])

    monkeypatch.setattr(util_module, "scrape_shopee_product", fake_scrape)
    r = client.post(
        "/api/util/test-shopee",
        json={
            "url": "https://shopee.co.id/product/1/2",
            "cookie": "SPC_EC=xyz",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "Test Item" in body["message"]
    assert seen["cookie"] == "SPC_EC=xyz"


# ---------------------------------------------------------------------------
# Subtitle SRT generation
# ---------------------------------------------------------------------------


def test_split_subtitle_segments_basic():
    text = "Halo semua! Ini produk bagus banget. Harganya cuma 50 ribu."
    segs = slideshow_mod._split_subtitle_segments(text)
    assert segs == [
        "Halo semua!",
        "Ini produk bagus banget.",
        "Harganya cuma 50 ribu.",
    ]


def test_split_subtitle_segments_breaks_long_runs_at_commas():
    long = (
        "Produk ini sangat bagus dengan kualitas premium yang tahan lama, "
        "harga terjangkau, dan stoknya terbatas hari ini saja jadi cepat order"
    )
    segs = slideshow_mod._split_subtitle_segments(long)
    # Should produce >1 segment by breaking at commas in the >80-char run.
    assert len(segs) >= 2
    assert all(seg.strip() for seg in segs)


def test_split_subtitle_segments_empty_input():
    assert slideshow_mod._split_subtitle_segments("") == []
    assert slideshow_mod._split_subtitle_segments("   \n  ") == []


def test_format_srt_timestamp_milliseconds():
    assert slideshow_mod._format_srt_timestamp(0) == "00:00:00,000"
    assert slideshow_mod._format_srt_timestamp(1.5) == "00:00:01,500"
    assert slideshow_mod._format_srt_timestamp(61.234) == "00:01:01,234"
    assert slideshow_mod._format_srt_timestamp(3661.001) == "01:01:01,001"


def test_format_srt_timestamp_carries_rounding_to_minute_and_hour():
    """Regression test: rounding 59.9999 -> 60.000 must propagate up."""

    # 59.9999 used to emit "00:00:60,000" (invalid SRT — libass skips it).
    assert slideshow_mod._format_srt_timestamp(59.9999) == "00:01:00,000"
    # 119.9999 sits on a minute boundary too.
    assert slideshow_mod._format_srt_timestamp(119.9999) == "00:02:00,000"
    # 3599.9999 must roll all the way up to the next hour.
    assert slideshow_mod._format_srt_timestamp(3599.9999) == "01:00:00,000"


def test_build_srt_distributes_by_char_weight():
    segs = ["short", "a much longer second sentence here"]
    srt = slideshow_mod._build_srt(segs, total_duration=10.0)
    # SRT structure: index, timestamp, text, blank line per cue.
    assert srt.startswith("1\n")
    assert "00:00:00,000 -->" in srt
    assert "short" in srt
    assert "a much longer second sentence here" in srt
    # Two cues -> "2\n" appears as the second cue's index marker.
    assert "\n2\n" in srt


def test_build_srt_clamps_per_segment_duration():
    """Single-character segments should take >=1s so they're readable."""

    segs = ["a", "b", "c"]
    srt = slideshow_mod._build_srt(segs, total_duration=0.5)
    # First cue starts at 0, ends at >=1.0 (clamp floor).
    first_block = srt.split("\n\n")[0]
    end_ts = first_block.splitlines()[1].split(" --> ")[1]
    # 00:00:01,xxx or later
    h, m, rest = end_ts.split(":")
    assert int(h) == 0 and int(m) == 0
    sec = float(rest.replace(",", "."))
    assert sec >= 1.0
