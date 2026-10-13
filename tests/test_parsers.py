from pathlib import Path

import pytest

from pricewatch.fetch import decode_html
from pricewatch.models import Listing
from pricewatch.parsers import find_site, get_parser, site_name_for_url
from pricewatch.parsers.base import parse_point_rate, parse_points, parse_yen

FIX = Path(__file__).parent / "fixtures"


def listing(url, shop=""):
    return Listing(site="", shop=shop, product="FIT 4 White", url=url)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("￥16,414", 16414),
        ("16,414円", 16414),
        ("１６，４１４円（税込）", 16414),
        ("¥ 21,582", 21582),
        ("19010", 19010),
        ("価格なし", None),
        (None, None),
    ],
)
def test_parse_yen(text, expected):
    assert parse_yen(text) == expected


def test_parse_points_and_rate():
    assert parse_points("190ポイント(1倍)") == 190
    assert parse_points("164pt (1%)") == 164
    assert parse_point_rate("10%ポイント還元") == 10
    assert parse_point_rate("獲得ポイント 193円相当（1%）") is None


def test_site_detection():
    assert find_site("https://www.amazon.co.jp/dp/B000").name == "Amazon.co.jp"
    assert site_name_for_url("https://item.rakuten.co.jp/shop/item/") == "楽天市場"
    assert site_name_for_url("https://store.shopping.yahoo.co.jp/x/y.html") == "Yahoo!ショッピング"
    assert site_name_for_url("https://www.sofmap.com/product_detail.aspx?sku=1") == "ソフマップ"
    assert site_name_for_url("https://example.jp/item") == "example.jp"


def test_amazon():
    url = "https://www.amazon.co.jp/dp/B000"
    r = get_parser(url).parse((FIX / "amazon.html").read_text(), listing(url))
    assert (r.price, r.points, r.effective, r.in_stock) == (16414, 164, 16250, True)


def test_rakuten():
    url = "https://item.rakuten.co.jp/shop/item/"
    r = get_parser(url).parse((FIX / "rakuten.html").read_text(), listing(url))
    assert (r.price, r.points, r.effective) == (19010, 190, 18820)


def test_jsonld_fallback_and_points_generic():
    url = "https://store.shopping.yahoo.co.jp/shop/item.html"
    r = get_parser(url).parse((FIX / "yahoo_jsonld.html").read_text(), listing(url))
    assert r.price == 19342
    assert r.raw["price_source"] == "json-ld"
    assert r.in_stock is True


def test_out_of_stock():
    url = "https://www.edion.com/item"
    r = get_parser(url).parse((FIX / "soldout.html").read_text(), listing(url))
    assert r.in_stock is False


def test_kakaku_shift_jis_and_shop_rows():
    html = decode_html((FIX / "kakaku_sjis.html").read_bytes(), "ISO-8859-1")
    url = "https://kakaku.com/item/K0001234567/"
    p = get_parser(url)
    sofmap = p.parse(html, listing(url, "ソフマップ.com"))
    yamada = p.parse(html, listing(url, "ヤマダウェブコム"))
    ec = p.parse(html, listing(url, "ECカレント"))
    missing = p.parse(html, listing(url, "Joshin"))
    assert (sofmap.price, sofmap.points) == (16315, 0)
    assert (yamada.price, yamada.points, yamada.effective) == (16414, 164, 16250)
    assert ec.price == 18027
    assert missing.price is None and missing.error == "shop_not_listed"
