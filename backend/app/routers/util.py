"""Utility endpoints used by the desktop frontend.

The Tauri WebView serves the frontend from `tauri.localhost`, so it cannot
fetch cross-origin Shopee CDN images directly (CORS + tightened CSP). The
backend acts as a proxy for those fetches, and exposes a health probe under
`/api/...` so the same prefix the frontend uses for everything else also
works for the splash readiness check.
"""

from __future__ import annotations

import base64

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
# resizes images server-side anyway.
_MAX_BYTES = 12 * 1024 * 1024  # 12 MB


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Mirror of the root `/healthz` reachable under the `/api` prefix."""

    return {"status": "ok"}


@router.post("/fetch-image", response_model=FetchImageResponse)
async def fetch_image(req: FetchImageRequest) -> FetchImageResponse:
    """Download a remote image server-side and return it as base64.

    Used by the frontend for scraped Shopee CDN images (which don't ship
    permissive CORS headers, and would also be blocked by the Tauri CSP).
    """

    target = str(req.url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            r = await client.get(
                target,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"fetch failed: {exc}") from exc

    if r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"upstream HTTP {r.status_code} fetching {target}",
        )

    body = r.content
    if len(body) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"image too large ({len(body)} bytes, max {_MAX_BYTES})",
        )

    return FetchImageResponse(
        image_b64=base64.b64encode(body).decode("ascii"),
        content_type=r.headers.get("content-type"),
    )
