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
