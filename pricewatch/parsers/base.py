"""価格・ポイント・在庫を HTML から抜き出す共通処理。"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from ..models import Listing, PriceResult

_YEN_RE = re.compile(r"(?:[¥￥]\s*)?(\d{1,3}(?:,\d{3})+|\d+)(?:\s*円)?")
_YEN_STRICT_RE = re.compile(r"[¥￥]\s*(\d{1,3}(?:,\d{3})+|\d+)|(\d{1,3}(?:,\d{3})+|\d+)\s*円")
_POINT_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s*(?:ポイント|pt|ＰＴ|PT|P(?![a-zA-Z]))")
_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]\s*(?:ポイント)?(?:還元|ポイント)")

OUT_OF_STOCK_WORDS = (
    "在庫切れ",
    "売り切れ",
    "売切れ",
    "品切れ",
    "在庫なし",
    "在庫がありません",
    "販売終了",
    "販売を終了",
    "入荷待ち",
    "お取り扱いできません",
    "取り扱いを終了",
    "SOLD OUT",
)

# 価格として現実的な範囲（誤検出対策）
MIN_PRICE = 1
MAX_PRICE = 50_000_000


def normalize(text: str) -> str:
    """全角→半角、空白除去、小文字化。店舗名の照合にも使う。"""
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", "", text).lower()


def parse_yen(text: str | None, strict: bool = False) -> int | None:
    """'￥16,414' '16,414円' '１６，４１４円' などを int に。"""
    if text is None:
        return None
    text = unicodedata.normalize("NFKC", str(text))
    m = (_YEN_STRICT_RE if strict else _YEN_RE).search(text)
    if not m:
        return None
    digits = next(g for g in m.groups() if g) if m.groups() else m.group(0)
    try:
        value = int(digits.replace(",", ""))
    except ValueError:
        return None
    return value if MIN_PRICE <= value <= MAX_PRICE else None


def parse_points(text: str | None) -> int | None:
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text)
    m = _POINT_RE.search(text)
    return int(m.group(1).replace(",", "")) if m else None


def parse_point_rate(text: str | None) -> float | None:
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text)
    m = _RATE_RE.search(text)
    return float(m.group(1)) if m else None


def points_from_rate(price: int, rate: float) -> int:
    return math.floor(price * rate / 100)


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _iter_jsonld(soup: BeautifulSoup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                for key in ("@graph", "offers", "mainEntity", "itemOffered"):
                    if key in node:
                        stack.append(node[key])


def extract_jsonld(soup: BeautifulSoup) -> tuple[int | None, bool | None]:
    """schema.org の Offer から価格と在庫を取得。"""
    for node in _iter_jsonld(soup):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if not any(t in ("Offer", "AggregateOffer") for t in types):
            continue
        raw = node.get("price", node.get("lowPrice"))
        if raw is None and isinstance(node.get("priceSpecification"), dict):
            raw = node["priceSpecification"].get("price")
        price = parse_yen(str(raw)) if raw is not None else None
        if price is None:
            continue
        availability = str(node.get("availability", ""))
        in_stock = None
        if availability:
            in_stock = not any(k in availability for k in ("OutOfStock", "SoldOut", "Discontinued"))
        return price, in_stock
    return None, None


def extract_meta_price(soup: BeautifulSoup) -> int | None:
    selectors = (
        'meta[itemprop="price"]',
        'meta[property="product:price:amount"]',
        'meta[property="og:price:amount"]',
    )
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag and tag.get("content"):
            price = parse_yen(tag["content"])
            if price is not None:
                return price
    tag = soup.select_one('[itemprop="price"]')
    if tag:
        return parse_yen(tag.get("content") or tag.get_text(" ", strip=True))
    return None


def first_text(soup: BeautifulSoup | Tag, selectors: list[str]) -> tuple[str | None, str | None]:
    """セレクタを順に試し、最初に見つかった要素のテキストと使ったセレクタを返す。"""
    for sel in selectors:
        try:
            tag = soup.select_one(sel)
        except Exception:  # 不正なセレクタは無視
            continue
        if tag is not None:
            text = tag.get("content") or tag.get_text(" ", strip=True)
            if text:
                return text, sel
    return None, None


def find_points_generic(soup: BeautifulSoup | Tag, price: int | None) -> int | None:
    """class / id に point を含む要素から「○○ポイント」「○%還元」を探す。"""
    candidates = soup.find_all(
        lambda t: isinstance(t, Tag)
        and any("point" in str(v).lower() for v in (t.get("class") or []) + [t.get("id") or ""])
    )
    for tag in candidates:
        text = tag.get_text(" ", strip=True)
        if len(text) > 200:
            continue
        pts = parse_points(text)
        if pts is not None and (price is None or pts < price):
            return pts
        rate = parse_point_rate(text)
        if rate is not None and price is not None:
            return points_from_rate(price, rate)
    return None


def text_says_out_of_stock(text: str | None) -> bool:
    if not text:
        return False
    norm = unicodedata.normalize("NFKC", text).upper()
    return any(unicodedata.normalize("NFKC", w).upper() in norm for w in OUT_OF_STOCK_WORDS)


@dataclass
class SiteConfig:
    name: str
    domains: tuple[str, ...]
    price_selectors: list[str] = field(default_factory=list)
    point_selectors: list[str] = field(default_factory=list)
    stock_selectors: list[str] = field(default_factory=list)
    # True のサイトは JS 描画やボット対策が強く、ブラウザ取得を推奨
    prefers_browser: bool = False


class Parser:
    """サイト設定に従って1商品ページを解析する汎用パーサ。"""

    def __init__(self, config: SiteConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    def parse(self, html: str, listing: Listing | None = None) -> PriceResult:
        soup = make_soup(html)
        return self.parse_soup(soup, listing)

    def parse_soup(self, soup: BeautifulSoup, listing: Listing | None = None) -> PriceResult:
        cfg = self.config
        raw: dict = {}

        # 1) サイト固有セレクタ（表示価格に最も近い）
        #    "[class*=...]" のような曖昧なセレクタは誤検出しやすいので構造化データの後に回す
        specific = [s for s in cfg.price_selectors if "*=" not in s]
        broad = [s for s in cfg.price_selectors if "*=" in s]
        price = None
        text, sel = first_text(soup, specific)
        if text:
            price = parse_yen(text)
            raw["price_source"] = sel

        # 2) 構造化データ
        ld_price, ld_stock = extract_jsonld(soup)
        if price is None and ld_price is not None:
            price, raw["price_source"] = ld_price, "json-ld"
        if price is None:
            price = extract_meta_price(soup)
            if price is not None:
                raw["price_source"] = "meta"

        # 3) 曖昧なセレクタ
        if price is None:
            text, sel = first_text(soup, broad)
            if text:
                price = parse_yen(text)
                raw["price_source"] = sel

        # ポイント
        points = None
        ptext, psel = first_text(soup, cfg.point_selectors)
        if ptext:
            points = parse_points(ptext)
            if points is None and price is not None:
                rate = parse_point_rate(ptext)
                if rate is not None:
                    points = points_from_rate(price, rate)
            if points is not None:
                raw["points_source"] = psel
        if points is None:
            points = find_points_generic(soup, price)
            if points is not None:
                raw["points_source"] = "generic"

        # 在庫
        in_stock = ld_stock
        stext, _ = first_text(soup, cfg.stock_selectors)
        if stext is not None:
            in_stock = not text_says_out_of_stock(stext)
        if price is None and in_stock is None:
            body = soup.body.get_text(" ", strip=True) if soup.body else ""
            if text_says_out_of_stock(body[:20000]):
                in_stock = False

        result = PriceResult(price=price, points=points or 0, in_stock=in_stock, raw=raw)
        if price is None:
            result.error = "out_of_stock" if in_stock is False else "price_not_found"
        return result
