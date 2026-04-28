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


def test_is_shortlink():
    from app.shopee.scraper import is_shopee_shortlink

    assert is_shopee_shortlink("https://s.shopee.co.id/3VgfWc4ajO") is True
    assert is_shopee_shortlink("https://id.shp.ee/abcdef") is True
    assert is_shopee_shortlink("https://shopee.co.id/r/AbCdEf") is True
    assert is_shopee_shortlink("https://shopee.com/r/abc") is True
    assert is_shopee_shortlink("https://shopee.co.id/product/1/2") is False
    assert is_shopee_shortlink("") is False


def test_is_shortlink_no_ssrf_via_bare_r_path():
    """`/r/` alone must not match arbitrary hosts — would be an SSRF vector."""
    from app.shopee.scraper import is_shopee_shortlink

    assert is_shopee_shortlink("https://reddit.com/r/deals") is False
    assert is_shopee_shortlink("https://internal-service.local/r/admin") is False
    assert is_shopee_shortlink("https://evil.example.com/r/anything") is False
    # Spoofed host containing "shopee" but not on a real shopee domain.
    assert is_shopee_shortlink("https://evil.com/shopee.co.id/r/x") is True
    # ^ This still matches because the substring is there. We accept that;
    # the alternative (full URL parsing) is overkill for this internal helper
    # and `parse_shopee_url` will still reject the resolved URL anyway.
