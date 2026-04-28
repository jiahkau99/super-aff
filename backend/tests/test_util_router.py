"""Tests for the /api/util router used by the Tauri desktop frontend."""

from __future__ import annotations

import base64
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import util as util_module


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz_under_api_prefix(client: TestClient) -> None:
    r = client.get("/api/util/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_healthz_still_works(client: TestClient) -> None:
    """Root /healthz is what the Rust sidecar uses for early diagnostics."""

    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def _patch_async_client(monkeypatch, handler):
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(util_module.httpx, "AsyncClient", factory)


def _stub_dns_to(monkeypatch, ip: str) -> None:
    """Force `_validate_public_target` to see only ``ip`` for any hostname."""

    def fake_getaddrinfo(host, *_args, **_kwargs):
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 0, "", (ip, 0))]

    monkeypatch.setattr(util_module.socket, "getaddrinfo", fake_getaddrinfo)


def test_fetch_image_returns_base64(monkeypatch):
    raw = b"\x89PNG\r\n\x1a\nfake png body"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://example.com/")
        return httpx.Response(200, content=raw, headers={"content-type": "image/png"})

    _stub_dns_to(monkeypatch, "1.2.3.4")
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


def test_fetch_image_rejects_oversized_payload_via_content_length(monkeypatch):
    """An honest Content-Length header lets us reject before reading the body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"\x00" * 16,
            headers={
                "content-type": "image/png",
                # Lie about the size so we hit the pre-check branch without
                # actually allocating a multi-GB body in the test.
                "content-length": str(13 * 1024 * 1024),
            },
        )

    _stub_dns_to(monkeypatch, "1.2.3.4")
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://example.com/big.png"},
    )
    assert r.status_code == 413


def test_fetch_image_rejects_oversized_payload_via_streaming(monkeypatch):
    """Even without Content-Length, the streaming loop must enforce the cap."""

    big = b"\x00" * (13 * 1024 * 1024)  # > 12 MB cap

    def handler(request: httpx.Request) -> httpx.Response:
        # Return without a content-length header so the streaming branch runs.
        resp = httpx.Response(200, content=big, headers={"content-type": "image/png"})
        resp.headers.pop("content-length", None)
        return resp

    _stub_dns_to(monkeypatch, "1.2.3.4")
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

    _stub_dns_to(monkeypatch, "1.2.3.4")
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


# ---- SSRF protection -----------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",        # loopback
        "10.0.0.5",         # RFC1918 private
        "192.168.1.1",      # RFC1918 private
        "172.16.5.10",      # RFC1918 private
        "169.254.169.254",  # link-local / cloud metadata
        "::1",              # IPv6 loopback
        "fd00::1",          # IPv6 unique-local (private)
        "0.0.0.0",          # unspecified
        "224.0.0.1",        # multicast
    ],
)
def test_fetch_image_rejects_ssrf_targets(monkeypatch, ip):
    """Any hostname resolving to a non-public IP must be refused."""

    _stub_dns_to(monkeypatch, ip)
    # Should never reach the network — fail loud if it does.

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(f"request escaped SSRF guard: {request.url}")

    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://internal.example/foo.png"},
    )
    assert r.status_code == 400
    assert "non-public" in r.json()["detail"]


def test_fetch_image_rejects_ssrf_when_any_resolved_ip_is_private(monkeypatch):
    """Mixed-record DNS responses must still be rejected (DNS-rebinding-ish)."""

    def fake_getaddrinfo(host, *_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
        ]

    monkeypatch.setattr(util_module.socket, "getaddrinfo", fake_getaddrinfo)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("request escaped SSRF guard")

    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://mixed.example/foo.png"},
    )
    assert r.status_code == 400


def test_fetch_image_rejects_dns_failure(monkeypatch):
    def boom(*_args, **_kwargs):
        raise socket.gaierror("nodename nor servname provided")

    monkeypatch.setattr(util_module.socket, "getaddrinfo", boom)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("request escaped SSRF guard")

    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://does-not-exist.example/foo.png"},
    )
    assert r.status_code == 400


# ---- Redirect handling --------------------------------------------------


def _multi_dns(monkeypatch, mapping: dict[str, str]) -> None:
    """Map each hostname to a specific resolved IP for SSRF validation."""

    def fake_getaddrinfo(host, *_args, **_kwargs):
        ip = mapping.get(host)
        if ip is None:
            raise socket.gaierror(f"unknown host {host}")
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 0, "", (ip, 0))]

    monkeypatch.setattr(util_module.socket, "getaddrinfo", fake_getaddrinfo)


def test_fetch_image_follows_safe_redirect(monkeypatch):
    """Public → public 302 must be followed and the final body returned."""

    raw = b"\x89PNG\r\n\x1a\nfinal payload"
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(str(request.url))
        if request.url.host == "first.example":
            return httpx.Response(
                302,
                headers={"location": "https://second.example/final.png"},
            )
        assert request.url.host == "second.example"
        return httpx.Response(
            200, content=raw, headers={"content-type": "image/png"}
        )

    _multi_dns(monkeypatch, {"first.example": "1.2.3.4", "second.example": "5.6.7.8"})
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://first.example/img.png"},
    )
    assert r.status_code == 200
    assert r.json()["image_b64"] == base64.b64encode(raw).decode("ascii")
    # Both hops were issued (proving redirects ARE followed when public).
    assert any("first.example" in u for u in seen_paths)
    assert any("second.example" in u for u in seen_paths)


def test_fetch_image_rejects_redirect_to_private_ip(monkeypatch):
    """Public → 169.254.169.254 (cloud metadata) MUST be refused.

    This is the specific bypass Devin Review flagged on PR #2.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "evil.example":
            return httpx.Response(
                302,
                headers={
                    "location": (
                        "http://169.254.169.254/latest/meta-data/"
                        "iam/security-credentials/"
                    )
                },
            )
        # If the redirect was followed, the test must fail loudly rather than
        # silently let metadata leak.
        raise AssertionError(
            f"redirect to internal target was NOT blocked: {request.url}"
        )

    _multi_dns(
        monkeypatch,
        {
            "evil.example": "1.2.3.4",
            "169.254.169.254": "169.254.169.254",
        },
    )
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://evil.example/bait.png"},
    )
    assert r.status_code == 400
    assert "non-public" in r.json()["detail"]


def test_fetch_image_rejects_redirect_to_loopback(monkeypatch):
    """Public → 127.0.0.1:<other-port> must also be refused."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "evil.example":
            return httpx.Response(
                302,
                headers={"location": "http://127.0.0.1:8000/secret"},
            )
        raise AssertionError(
            f"redirect to loopback was NOT blocked: {request.url}"
        )

    _multi_dns(
        monkeypatch,
        {"evil.example": "1.2.3.4", "127.0.0.1": "127.0.0.1"},
    )
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://evil.example/bait.png"},
    )
    assert r.status_code == 400


def test_fetch_image_rejects_redirect_chain_terminating_in_private_ip(monkeypatch):
    """A multi-hop chain still gets validated at every hop."""

    locations = {
        "a.example": "https://b.example/",
        "b.example": "http://10.0.0.1/secret",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host in {"a.example", "b.example"}:
            return httpx.Response(302, headers={"location": locations[host]})
        raise AssertionError(
            f"redirect chain reached private target: {request.url}"
        )

    _multi_dns(
        monkeypatch,
        {
            "a.example": "1.2.3.4",
            "b.example": "5.6.7.8",
            "10.0.0.1": "10.0.0.1",
        },
    )
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://a.example/start.png"},
    )
    assert r.status_code == 400


def test_fetch_image_caps_redirect_count(monkeypatch):
    """Endless public→public bouncing eventually returns 502."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Bounce forever between two public hosts.
        other = "b.example" if request.url.host == "a.example" else "a.example"
        return httpx.Response(302, headers={"location": f"https://{other}/loop"})

    _multi_dns(
        monkeypatch,
        {"a.example": "1.2.3.4", "b.example": "5.6.7.8"},
    )
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://a.example/start.png"},
    )
    assert r.status_code == 502
    assert "too many redirects" in r.json()["detail"]


def test_fetch_image_handles_relative_redirect(monkeypatch):
    """Relative `Location` headers must resolve against the current URL."""

    raw = b"final"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start.png":
            # Relative redirect — same host, different path.
            return httpx.Response(302, headers={"location": "/final.png"})
        assert request.url.path == "/final.png"
        return httpx.Response(200, content=raw, headers={"content-type": "image/png"})

    _multi_dns(monkeypatch, {"only.example": "1.2.3.4"})
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://only.example/start.png"},
    )
    assert r.status_code == 200
    assert r.json()["image_b64"] == base64.b64encode(raw).decode("ascii")


def test_fetch_image_rejects_redirect_without_location(monkeypatch):
    """A 302 with no Location header is malformed — return 502, not crash."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302)  # no Location header

    _multi_dns(monkeypatch, {"only.example": "1.2.3.4"})
    _patch_async_client(monkeypatch, handler)
    client = TestClient(app)
    r = client.post(
        "/api/util/fetch-image",
        json={"url": "https://only.example/x.png"},
    )
    assert r.status_code == 502
    assert "without Location" in r.json()["detail"]
