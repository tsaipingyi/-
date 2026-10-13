from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now_jst() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


@dataclass
class Listing:
    """監視対象の1行（サイト × 店舗 × 商品）。スプレッドシートの1行に相当。"""

    site: str
    shop: str
    product: str
    url: str
    alert_price1: int | None = None
    alert_price2: int | None = None
    # ポイント還元率(%)を手動指定する場合に使う。指定時はページから取得したポイントより優先。
    point_rate: float | None = None
    active: bool = True
    id: int | None = None


@dataclass
class PriceResult:
    """1回の取得結果。"""

    price: int | None = None
    points: int = 0
    in_stock: bool | None = None
    error: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.price is not None and self.error is None

    @property
    def effective(self) -> int | None:
        """商品価格 − ポイント（スプレッドシートの「商品価格-ポイント」）。"""
        if self.price is None:
            return None
        return self.price - (self.points or 0)


@dataclass
class Snapshot:
    listing_id: int
    run_id: int
    checked_at: datetime
    price: int | None
    points: int
    effective: int | None
    in_stock: bool | None
    error: str | None
