"""Batch CSV planning endpoint.

This endpoint *does not* run the full pipeline server-side — running 50
products through LLM + TTS + ffmpeg in one request would be too slow and
would also require the user's API keys to be sent in one giant blob.

Instead, the backend takes a CSV (parsed client-side into rows) and:
  1. For each row with a Shopee URL, scrapes the product info.
  2. Returns a normalized list of "items" the frontend then iterates over,
     calling /api/content/generate, /api/voiceover/generate, and
     /api/compose/slideshow per item with a progress UI.

This keeps the pipeline cancellable and lets us surface per-row errors
clearly.
"""

from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter

from app.schemas import BatchPlanRequest, BatchPlanResponse
from app.shopee import scrape_shopee_product

router = APIRouter(prefix="/api/batch", tags=["batch"])


async def _resolve_row(row, *, sem: asyncio.Semaphore) -> dict:
    out: dict = {
        "url": row.url,
        "title": row.judul,
        "description": row.deskripsi,
        "images": [],
        "price": None,
        "ok": True,
        "error": None,
    }
    if not row.url.strip():
        if not row.judul.strip():
            out["ok"] = False
            out["error"] = "Baris kosong: butuh url atau judul."
        return out

    async with sem:
        try:
            product = await scrape_shopee_product(row.url)
        except (ValueError, httpx.HTTPError) as exc:
            out["ok"] = False
            out["error"] = (
                f"Scrape gagal: {exc}. Bisa dilanjut manual dengan isi judul + foto sendiri."
            )
            return out

    out["title"] = product.title or row.judul
    out["description"] = product.description or row.deskripsi
    out["images"] = product.images
    out["price"] = product.price
    return out


@router.post("/plan", response_model=BatchPlanResponse)
async def plan(req: BatchPlanRequest) -> BatchPlanResponse:
    """Resolve each CSV row into a normalized item ready for per-row processing."""
    sem = asyncio.Semaphore(4)  # cap parallel Shopee requests
    results = await asyncio.gather(*(_resolve_row(r, sem=sem) for r in req.rows))
    return BatchPlanResponse(items=list(results))
