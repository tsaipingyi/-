"""価格.com: 1つの商品ページに複数店舗が並ぶので、店舗名で行を特定する。"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from ..models import Listing, PriceResult
from .base import (
    Parser,
    SiteConfig,
    make_soup,
    normalize,
    parse_point_rate,
    parse_points,
    parse_yen,
    points_from_rate,
)

ROW_TAGS = ("tr", "li", "div")
SHOP_NAME_SELECTORS = (
    ".p-PTShopData_name",
    ".p-PTShop_name",
    ".shopname",
    "[class*='shopName']",
    "[class*='ShopName']",
    "[class*='shop_name']",
)
PRICE_SELECTORS = (".p-PTPrice_price", "[class*='Price_price']", ".priceTxt", ".fontPrice", "[class*='price']")
POINT_SELECTORS = (".p-PTPoint", "[class*='Point']", "[class*='point']")


class KakakuParser(Parser):
    def __init__(self, config: SiteConfig):
        super().__init__(config)

    def parse(self, html: str, listing: Listing | None = None) -> PriceResult:
        soup = make_soup(html)
        shop = listing.shop if listing else ""
        if not shop or normalize(shop) in ("価格.com", "kakaku.com"):
            # 店舗指定なし → ページの最安値
            return super().parse_soup(soup, listing)
        row = self.find_shop_row(soup, shop)
        if row is None:
            return PriceResult(error="shop_not_listed", in_stock=False)
        return self.parse_row(row)

    @staticmethod
    def find_shop_row(soup: BeautifulSoup, shop: str) -> Tag | None:
        target = normalize(shop)
        best: Tag | None = None
        best_len = None
        # まず店舗名専用の要素で照合
        for sel in SHOP_NAME_SELECTORS:
            for name_tag in soup.select(sel):
                if normalize(name_tag.get_text()) == target or target in normalize(name_tag.get_text()):
                    row = name_tag.find_parent(ROW_TAGS[0]) or name_tag.find_parent("li")
                    if row is not None and parse_yen(row.get_text(" "), strict=True):
                        return row
        # フォールバック: 店舗名と価格を両方含む最小の行要素
        for tag in soup.find_all(ROW_TAGS):
            text = tag.get_text(" ", strip=True)
            if target not in normalize(text):
                continue
            if parse_yen(text, strict=True) is None:
                continue
            if best_len is None or len(text) < best_len:
                best, best_len = tag, len(text)
        return best

    @staticmethod
    def parse_row(row: Tag) -> PriceResult:
        price = None
        for sel in PRICE_SELECTORS:
            tag = row.select_one(sel)
            if tag is not None:
                price = parse_yen(tag.get_text(" ", strip=True), strict=True)
                if price is not None:
                    break
        if price is None:
            price = parse_yen(row.get_text(" ", strip=True), strict=True)

        points = None
        for sel in POINT_SELECTORS:
            tag = row.select_one(sel)
            if tag is None:
                continue
            text = tag.get_text(" ", strip=True)
            points = parse_points(text)
            if points is None and price is not None:
                rate = parse_point_rate(text)
                if rate is not None:
                    points = points_from_rate(price, rate)
            if points is not None:
                break

        result = PriceResult(price=price, points=points or 0, in_stock=price is not None, raw={"price_source": "kakaku-row"})
        if price is None:
            result.error = "price_not_found"
        return result
