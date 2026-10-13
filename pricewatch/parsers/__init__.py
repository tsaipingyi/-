"""URL のドメインから対応するパーサを選ぶ。

各サイトのセレクタはサイト側のデザイン変更で効かなくなることがある。
その場合でも JSON-LD / meta タグからのフォールバックで取れることが多いが、
取れなくなったら `pricewatch test-url <URL>` で確認し、ここのセレクタを調整する。
"""

from __future__ import annotations

from urllib.parse import urlparse

from .base import Parser, SiteConfig
from .kakaku import KakakuParser

SITES: list[SiteConfig] = [
    SiteConfig(
        name="Amazon.co.jp",
        domains=("amazon.co.jp",),
        price_selectors=[
            "#corePrice_feature_div .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#apex_desktop .a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#price_inside_buybox",
        ],
        point_selectors=["#points_feature_div", "#pointsInsideBuyBox_feature_div", ".loyalty-points"],
        stock_selectors=["#availability"],
        prefers_browser=True,
    ),
    SiteConfig(
        name="楽天市場",
        domains=("item.rakuten.co.jp", "rakuten.co.jp"),
        price_selectors=[
            "[class*='price--OX_YW']",
            "[class*='number-display'] [class*='value']",
            ".price2",
        ],
        point_selectors=["[class*='point-summary']", "[class*='point-display']", ".point-up", "#js-point"],
        stock_selectors=["[class*='soldout']", ".soldout_msg"],
    ),
    SiteConfig(
        name="Yahoo!ショッピング",
        domains=("store.shopping.yahoo.co.jp", "shopping.yahoo.co.jp", "paypaymall.yahoo.co.jp"),
        price_selectors=[".elPriceNumber", "[class*='ItemPrice'] [class*='number']", "[class*='styles_price']"],
        point_selectors=[".elGetPoint", "[class*='PointInfo']", "[class*='styles_point']", ".elPointTotal"],
        stock_selectors=[".elStock", "[class*='Stock']"],
    ),
    SiteConfig(
        name="価格.com",
        domains=("kakaku.com",),
        price_selectors=[".priceTxt", ".p-PTPrice_price", "#minPrice"],
    ),
    SiteConfig(
        name="ビックカメラ",
        domains=("biccamera.com",),
        price_selectors=[".bcs_price .val", ".bcs_price", "[class*='price'] [class*='val']"],
        point_selectors=[".bcs_point", "[class*='point']"],
        stock_selectors=[".bcs_stock", "[class*='stock']"],
    ),
    SiteConfig(
        name="コジマネット",
        domains=("kojima.net",),
        price_selectors=[".price .num", ".price", "[class*='price']"],
        point_selectors=[".point", "[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="ヤマダウェブコム",
        domains=("yamada-denkiweb.com",),
        price_selectors=[".highlight.x-large", ".item-price", "[class*='price']"],
        point_selectors=[".point", "[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="ECカレント",
        domains=("ec-current.com",),
        price_selectors=[".price", "[class*='price']"],
        point_selectors=["[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="ソフマップ",
        domains=("sofmap.com",),
        price_selectors=["#product_price", ".product_price", ".price strong", "[class*='price']"],
        point_selectors=["#product_point", ".point", "[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="Joshin",
        domains=("joshinweb.jp",),
        price_selectors=[".fsL strong", ".fsL", "[class*='price']"],
        point_selectors=["[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="エディオン",
        domains=("edion.com",),
        price_selectors=[".price-num", ".price", "[class*='price']"],
        point_selectors=["[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="Nojima",
        domains=("online.nojima.co.jp", "nojima.co.jp"),
        price_selectors=[".price", "[class*='price']"],
        point_selectors=["[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="e-best",
        domains=("ebest.co.jp",),
        price_selectors=[".price", "[class*='price']"],
        point_selectors=["[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
    SiteConfig(
        name="特価COM",
        domains=("tokka.com",),
        price_selectors=[".price", "[class*='price']"],
        point_selectors=["[class*='point']"],
        stock_selectors=["[class*='stock']"],
    ),
]

GENERIC = SiteConfig(name="その他", domains=())


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def find_site(url: str) -> SiteConfig:
    host = _domain(url)
    for site in SITES:
        if any(host == d or host.endswith("." + d) for d in site.domains):
            return site
    return GENERIC


def site_name_for_url(url: str) -> str:
    site = find_site(url)
    return site.name if site is not GENERIC else (_domain(url) or "その他")


def get_parser(url: str) -> Parser:
    site = find_site(url)
    if site.name == "価格.com":
        return KakakuParser(site)
    return Parser(site)


__all__ = ["SITES", "Parser", "SiteConfig", "find_site", "get_parser", "site_name_for_url"]
