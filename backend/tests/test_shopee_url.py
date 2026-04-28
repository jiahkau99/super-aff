from app.shopee.scraper import parse_shopee_url


def test_parse_product_path():
    ids = parse_shopee_url("https://shopee.co.id/product/123456/789012")
    assert ids is not None
    assert ids.shop_id == 123456
    assert ids.item_id == 789012
    assert ids.domain == "shopee.co.id"


def test_parse_i_path():
    ids = parse_shopee_url(
        "https://shopee.co.id/Celana-Jeans-Pria-Skinny-i.111111.222222"
    )
    assert ids is not None
    assert ids.shop_id == 111111
    assert ids.item_id == 222222


def test_parse_bare_ids():
    ids = parse_shopee_url("123/456")
    assert ids is not None
    assert ids.shop_id == 123
    assert ids.item_id == 456


def test_parse_invalid():
    assert parse_shopee_url("https://google.com") is None
    assert parse_shopee_url("") is None
    assert parse_shopee_url("not a url") is None


def test_parse_other_domain():
    ids = parse_shopee_url("https://shopee.sg/product/1/2")
    assert ids is not None
    assert ids.domain == "shopee.sg"


def test_parse_affiliate_path():
    """Affiliate-style URL: /<slug>/<shop_id>/<item_id>."""
    ids = parse_shopee_url("https://shopee.co.id/opaanlp/926472192/43171429168")
    assert ids is not None
    assert ids.shop_id == 926472192
    assert ids.item_id == 43171429168


def test_parse_affiliate_path_with_query():
    ids = parse_shopee_url(
        "https://shopee.co.id/myshop/12345/67890?utm_source=affiliate"
    )
    assert ids is not None
    assert ids.shop_id == 12345
    assert ids.item_id == 67890


def test_affiliate_path_doesnt_match_homepage_handle():
    # /buyer/account/profile shouldn't accidentally match — the second segment
    # must be all digits.
    assert parse_shopee_url("https://shopee.co.id/buyer/account/profile") is None


def test_is_shortlink_no_ssrf_via_bare_r_path():
    """`/r/` alone must not match arbitrary hosts — would be an SSRF vector."""
    from app.shopee.scraper import is_shopee_shortlink

    assert is_shopee_shortlink("https://reddit.com/r/deals") is False
    assert is_shopee_shortlink("https://internal-service.local/r/admin") is False
    assert is_shopee_shortlink("https://evil.example.com/r/anything") is False


def test_is_shortlink_no_ssrf_via_subdomain_or_path_substring():
    """Hostname must equal a Shopee shortlink host — substring matches must NOT
    trigger resolve_shortlink (SSRF protection)."""
    from app.shopee.scraper import is_shopee_shortlink

    # Attacker host that contains "s.shopee." as substring of subdomain.
    assert is_shopee_shortlink("https://news.shopee.evil.com/anything") is False
    # Attacker host that contains "id.shp.ee" as substring.
    assert is_shopee_shortlink("https://android.shp.ee.evil.com/") is False
    # Path-based spoof: real shortlink string lives in path, not hostname.
    assert is_shopee_shortlink("https://evil.com/shopee.co.id/r/x") is False
    assert is_shopee_shortlink("https://evil.com/?u=https://s.shopee.co.id/x") is False
    # Non-http(s) schemes must be rejected.
    assert is_shopee_shortlink("file:///etc/passwd") is False
    assert is_shopee_shortlink("javascript:alert(1)") is False
    # Empty / malformed.
    assert is_shopee_shortlink("not a url") is False


def test_is_shortlink_accepts_real_hosts():
    from app.shopee.scraper import is_shopee_shortlink

    assert is_shopee_shortlink("https://s.shopee.co.id/3VgfWc4ajO") is True
    assert is_shopee_shortlink("https://s.shopee.com/anything") is True
    assert is_shopee_shortlink("https://id.shp.ee/abcdef") is True
    assert is_shopee_shortlink("https://shopee.co.id/r/AbCdEf") is True
    assert is_shopee_shortlink("https://www.shopee.co.id/r/AbCdEf") is True
    # Marketplace host with non-/r/ path is NOT a shortlink (it's a real URL).
    assert is_shopee_shortlink("https://shopee.co.id/product/1/2") is False
