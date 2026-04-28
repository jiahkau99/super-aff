"""Utility endpoints used by the desktop frontend.

The Tauri WebView serves the frontend from `tauri.localhost`, so it cannot
fetch cross-origin Shopee CDN images directly (CORS + tightened CSP). The
backend acts as a proxy for those fetches, and exposes a health probe under
`/api/...` so the same prefix the frontend uses for everything else also
works for the splash readiness check.
"""

from __future__ import annotations

import base64
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

router = APIRouter(prefix="/api/util", tags=["util"])


class FetchImageRequest(BaseModel):
    url: HttpUrl = Field(..., description="Remote image URL to download.")


class FetchImageResponse(BaseModel):
    image_b64: str
    content_type: str | None = None


# Cap downloaded payloads to keep memory bounded — the slideshow composer
# resizes images server-side anyway. We enforce this *while streaming* so a
# multi-GB upstream response cannot exhaust memory before the check runs.
_MAX_BYTES = 12 * 1024 * 1024  # 12 MB
_STREAM_CHUNK = 64 * 1024


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Mirror of the root `/healthz` reachable under the `/api` prefix."""

    return {"status": "ok"}


def _validate_public_target(target_url: str) -> None:
    """Reject SSRF-prone targets.

    The desktop sidecar binds to 127.0.0.1 with permissive CORS, so any
    website the user visits in their browser could POST here. Without
    validation, this endpoint would be an open SSRF proxy into the user's
    LAN, cloud metadata services, and other localhost ports.

    Rules:
      * Scheme must be http(s) — Pydantic's HttpUrl already covers this, but
        we re-check defensively.
      * Hostname must resolve to ONLY public IP addresses. Reject if any of
        the resolved A/AAAA records is private, loopback, link-local,
        reserved, or multicast — any of those is enough to refuse the
        request.
    """

    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="only http(s) URLs allowed")
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail="missing hostname")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail=f"DNS lookup failed: {exc}") from exc

    if not infos:
        raise HTTPException(status_code=400, detail="no DNS records resolved")

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Should never happen for getaddrinfo output, but be defensive.
            raise HTTPException(
                status_code=400, detail=f"unparseable resolved IP {ip_str!r}"
            ) from None
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(
                status_code=400,
                detail=f"refusing to fetch non-public address {ip_str}",
            )


@router.post("/fetch-image", response_model=FetchImageResponse)
async def fetch_image(req: FetchImageRequest) -> FetchImageResponse:
    """Download a remote image server-side and return it as base64.

    Used by the frontend for scraped Shopee CDN images (which don't ship
    permissive CORS headers, and would also be blocked by the Tauri CSP).
    """

    target = str(req.url)
    _validate_public_target(target)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            async with client.stream("GET", target, headers=headers) as r:
                if r.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"upstream HTTP {r.status_code} fetching {target}",
                    )

                # Cheap pre-check; some upstreams send accurate Content-Length.
                cl = r.headers.get("content-length")
                if cl is not None:
                    try:
                        if int(cl) > _MAX_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail=(
                                    f"image too large ({cl} bytes declared, "
                                    f"max {_MAX_BYTES})"
                                ),
                            )
                    except ValueError:
                        pass  # ignore malformed Content-Length

                content_type = r.headers.get("content-type")
                buf = bytearray()
                async for chunk in r.aiter_bytes(chunk_size=_STREAM_CHUNK):
                    if len(buf) + len(chunk) > _MAX_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"image too large (>{_MAX_BYTES} bytes)",
                        )
                    buf.extend(chunk)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"fetch failed: {exc}") from exc

    return FetchImageResponse(
        image_b64=base64.b64encode(bytes(buf)).decode("ascii"),
        content_type=content_type,
    )
