"""Best-effort Shopee product scraper.

Shopee exposes a public item API at:
    https://shopee.co.id/api/v4/item/get?itemid=<id>&shopid=<id>

It does not require auth, but it is rate-limited and may block server-side
IPs. We do best-effort scraping; if Shopee blocks us, the frontend should
fall back to letting the user paste title/photos manually.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.schemas import ShopeeProduct

SHOPEE_DOMAINS = (
    "shopee.co.id",
    "shopee.com",
    "shopee.sg",
    "shopee.com.my",
    "shopee.tw",
    "shopee.ph",
    "shopee.vn",
    "shopee.co.th",
    "shopee.com.br",
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer": "https://shopee.co.id/",
    "X-API-SOURCE": "pc",
    "X-Requested-With": "XMLHttpRequest",
}


@dataclass(frozen=True)
class ShopeeIDs:
    shop_id: int
    item_id: int
    domain: str = "shopee.co.id"


_PRODUCT_PATH_RE = re.compile(r"/product/(\d+)/(\d+)")
_I_PATH_RE = re.compile(r"\.(\d+)\.(\d+)(?:[/?#]|$)")


def parse_shopee_url(url: str) -> ShopeeIDs | None:
    """Extract (shop_id, item_id) from common Shopee URL formats.

    Supports:
      - https://shopee.co.id/product/<shop_id>/<item_id>
      - https://shopee.co.id/<slug>-i.<shop_id>.<item_id>
      - bare ids: "<shop_id>/<item_id>"
    """
    s = url.strip()
    if not s:
        return None

    # Detect domain (default to .co.id)
    domain = "shopee.co.id"
    for d in SHOPEE_DOMAINS:
        if d in s:
            domain = d
            break

    m = _PRODUCT_PATH_RE.search(s)
    if m:
        return ShopeeIDs(shop_id=int(m.group(1)), item_id=int(m.group(2)), domain=domain)

    m = _I_PATH_RE.search(s)
    if m:
        return ShopeeIDs(shop_id=int(m.group(1)), item_id=int(m.group(2)), domain=domain)

    # Bare "<shop>/<item>"
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", s)
    if m:
        return ShopeeIDs(shop_id=int(m.group(1)), item_id=int(m.group(2)), domain=domain)

    return None


def _img_url(image_hash: str, domain: str) -> str:
    """Convert a Shopee image hash to a CDN URL."""
    # Use the Singapore CDN; works for all locales.
    return f"https://down-id.img.susercontent.com/file/{image_hash}"


async def scrape_shopee_product(url: str, *, timeout: float = 12.0) -> ShopeeProduct:
    """Fetch product info from Shopee. Raises httpx.HTTPError on failure."""
    ids = parse_shopee_url(url)
    if ids is None:
        raise ValueError(f"Tidak bisa mendeteksi shop_id/item_id dari URL: {url!r}")

    api = (
        f"https://{ids.domain}/api/v4/item/get"
        f"?itemid={ids.item_id}&shopid={ids.shop_id}"
    )

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(api, headers=DEFAULT_HEADERS)
        r.raise_for_status()
        payload = r.json()

    data = (payload or {}).get("data") or {}
    if not data:
        raise httpx.HTTPError(
            f"Shopee API merespon tanpa data (mungkin di-block / rate-limited): {payload!r:.200}"
        )

    title: str = data.get("name") or ""
    description: str = data.get("description") or ""
    price_min = data.get("price_min")
    price = int(price_min // 100000) if isinstance(price_min, int) else None  # micro-rupiah

    image_hashes: list[str] = list(data.get("images") or [])
    images = [_img_url(h, ids.domain) for h in image_hashes if h]

    rating = (data.get("item_rating") or {}).get("rating_star")
    sold = data.get("historical_sold")
    shop_name: str | None = None
    # data["shop_name"] is not always present, but data has shopid only.

    return ShopeeProduct(
        title=title,
        description=description,
        price=price,
        currency="IDR",
        images=images,
        rating_star=float(rating) if isinstance(rating, (int, float)) else None,
        historical_sold=int(sold) if isinstance(sold, int) else None,
        shop_name=shop_name,
        item_id=ids.item_id,
        shop_id=ids.shop_id,
        source_url=url,
    )
