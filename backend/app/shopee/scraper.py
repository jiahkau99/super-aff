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
from urllib.parse import urlparse

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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer": "https://shopee.co.id/",
    "X-API-SOURCE": "pc",
    "X-Requested-With": "XMLHttpRequest",
    # Browser fingerprint hints. These are tiny on their own but combined with
    # an authenticated `Cookie` they make the request look more like a real
    # tab and less like a stripped-down `requests` script.
    "sec-ch-ua": '"Chromium";v="126", "Not.A/Brand";v="24", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


def _build_headers(cookie: str | None) -> dict[str, str]:
    """Return DEFAULT_HEADERS optionally extended with a user-supplied Cookie.

    Empty / whitespace-only cookies are ignored so callers can blindly pass
    whatever was loaded from the frontend's localStorage without having to
    branch on "is the user logged in".
    """

    if cookie and cookie.strip():
        return {**DEFAULT_HEADERS, "Cookie": cookie.strip()}
    return dict(DEFAULT_HEADERS)


@dataclass(frozen=True)
class ShopeeIDs:
    shop_id: int
    item_id: int
    domain: str = "shopee.co.id"


_PRODUCT_PATH_RE = re.compile(r"/product/(\d+)/(\d+)")
_I_PATH_RE = re.compile(r"\.(\d+)\.(\d+)(?:[/?#]|$)")
# Affiliate-style URL: /<slug>/<shop_id>/<item_id> where slug is non-numeric.
# Examples: /opaanlp/926472192/43171429168, /myshop/12345/67890
_AFFILIATE_PATH_RE = re.compile(r"/[A-Za-z][A-Za-z0-9_-]*/(\d{4,})/(\d{4,})(?:[/?#]|$)")


# Hosts that are exclusively short-link hosts (any path is a redirect target).
_SHORTLINK_HOST_RE = re.compile(
    r"^(?:s\.shopee\.(?:co\.id|com|sg|com\.my|tw|ph|vn|co\.th|com\.br)"
    r"|id\.shp\.ee)$"
)
# Shopee marketplace hosts (with optional "www.") that use /r/<slug> as a
# short-link redirect path.
_SHOPEE_HOST_RE = re.compile(
    r"^(?:www\.)?shopee\.(?:co\.id|com|sg|com\.my|tw|ph|vn|co\.th|com\.br)$"
)


def is_shopee_shortlink(url: str) -> bool:
    """Return True if the URL is a known Shopee short-link that needs to be
    resolved (HTTP redirect followed) before parsing.

    Validation is hostname-based via :func:`urllib.parse.urlparse` — never
    substring matching — to prevent SSRF. URLs like
    ``https://news.shopee.evil.com/`` or ``https://android.shp.ee.evil.com/``
    must NOT match, even though their hostnames contain literal substrings of a
    shortlink host.
    """
    s = (url or "").strip()
    if not s:
        return False
    try:
        parsed = urlparse(s)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if _SHORTLINK_HOST_RE.match(host):
        return True
    # Marketplace-host /r/<slug> redirects (e.g. https://shopee.co.id/r/AbCdEf).
    if _SHOPEE_HOST_RE.match(host) and parsed.path.startswith("/r/"):
        return True
    return False


def parse_shopee_url(url: str) -> ShopeeIDs | None:
    """Extract (shop_id, item_id) from common Shopee URL formats.

    Supports:
      - https://shopee.co.id/product/<shop_id>/<item_id>
      - https://shopee.co.id/<slug>-i.<shop_id>.<item_id>
      - https://shopee.co.id/<shop_handle>/<shop_id>/<item_id>     (affiliate)
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

    m = _AFFILIATE_PATH_RE.search(s)
    if m:
        return ShopeeIDs(shop_id=int(m.group(1)), item_id=int(m.group(2)), domain=domain)

    # Bare "<shop>/<item>"
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", s)
    if m:
        return ShopeeIDs(shop_id=int(m.group(1)), item_id=int(m.group(2)), domain=domain)

    return None


async def resolve_shortlink(
    url: str, *, timeout: float = 8.0, cookie: str | None = None
) -> str:
    """Follow redirects and return the final URL.

    Used so callers can pass a Shopee short-link (s.shopee.co.id/...) and we
    can still parse the canonical product URL it expands to.
    """
    headers: dict[str, str] = {"User-Agent": DEFAULT_HEADERS["User-Agent"]}
    if cookie and cookie.strip():
        headers["Cookie"] = cookie.strip()
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        # Use a HEAD request first to be fast; fall back to GET if the host
        # rejects HEAD.
        try:
            r = await client.head(url)
            if r.status_code >= 400:
                r = await client.get(url)
        except httpx.HTTPError:
            r = await client.get(url)
        return str(r.url)


def _img_url(image_hash: str, domain: str) -> str:
    """Convert a Shopee image hash to a CDN URL."""
    # Use the Singapore CDN; works for all locales.
    return f"https://down-id.img.susercontent.com/file/{image_hash}"


async def scrape_shopee_product(
    url: str, *, timeout: float = 12.0, cookie: str | None = None
) -> ShopeeProduct:
    """Fetch product info from Shopee. Raises httpx.HTTPError on failure.

    If the URL is a short-link (s.shopee.co.id/...), it is resolved via a
    redirect-following HEAD request before parsing.

    ``cookie`` is an optional raw ``Cookie:`` header value supplied by the
    user (e.g. dumped from their browser DevTools). Shopee's anti-bot blocks
    a lot of unauthenticated server-side traffic, so an authenticated cookie
    drastically improves the success rate. Sent verbatim to ``shopee.co.id``
    only — never logged, never persisted.
    """
    canonical_url = url
    if is_shopee_shortlink(url):
        try:
            canonical_url = await resolve_shortlink(
                url, timeout=timeout, cookie=cookie
            )
        except httpx.HTTPError as exc:
            raise ValueError(f"Gagal resolve shortlink {url!r}: {exc}") from exc

    ids = parse_shopee_url(canonical_url)
    if ids is None:
        raise ValueError(
            f"Tidak bisa mendeteksi shop_id/item_id dari URL: {canonical_url!r}"
        )

    api = (
        f"https://{ids.domain}/api/v4/item/get"
        f"?itemid={ids.item_id}&shopid={ids.shop_id}"
    )

    headers = _build_headers(cookie)
    # Adjust Referer to match the locale-specific marketplace.
    headers["Referer"] = f"https://{ids.domain}/"

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(api, headers=headers)
        if r.status_code in (401, 403, 429):
            raise httpx.HTTPError(
                f"Shopee API menolak request (HTTP {r.status_code}). "
                "Server-side scraping di-block oleh anti-bot Shopee — "
                "lanjut isi judul + upload foto manual."
            )
        r.raise_for_status()
        try:
            payload = r.json()
        except ValueError as exc:
            raise httpx.HTTPError(
                f"Shopee API mengembalikan body non-JSON (mungkin halaman challenge): {exc}"
            ) from exc

    # Shopee returns HTTP 200 with an "error" code when anti-bot blocks the
    # request (e.g. error 90309999 = bot fingerprint mismatch). Surface it as
    # a clear message so the frontend can offer a manual-input fallback.
    err_code = (payload or {}).get("error")
    if err_code:
        raise httpx.HTTPError(
            f"Shopee API menolak request (error {err_code}). "
            "Server-side scraping di-block oleh anti-bot Shopee — "
            "lanjut isi judul + upload foto manual."
        )

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
        source_url=canonical_url,
    )
