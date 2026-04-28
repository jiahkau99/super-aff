from __future__ import annotations

import httpx
from fastapi import APIRouter

from app.schemas import ScrapeRequest, ScrapeResponse
from app.shopee import scrape_shopee_product

router = APIRouter(prefix="/api/shopee", tags=["shopee"])


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest) -> ScrapeResponse:
    """Best-effort scrape of a Shopee product URL.

    Returns ok=False with an error message on failure (instead of throwing)
    so the frontend can offer a manual-input fallback.
    """
    try:
        product = await scrape_shopee_product(req.url)
        return ScrapeResponse(ok=True, product=product)
    except ValueError as exc:
        return ScrapeResponse(ok=False, error=str(exc))
    except httpx.HTTPError as exc:
        return ScrapeResponse(
            ok=False,
            error=f"Gagal akses Shopee API: {exc}. Coba isi judul + foto manual.",
        )
    except Exception as exc:  # pragma: no cover - safety net
        return ScrapeResponse(ok=False, error=f"Error tak terduga: {exc!s}")
