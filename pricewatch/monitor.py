"""1回の巡回: 全監視対象を取得 → 保存 → 前回との差分・アラートを検出。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from .db import Database
from .fetch import Fetcher, FetchError
from .models import Listing, PriceResult, now_jst
from .parsers import get_parser
from .parsers.base import points_from_rate

log = logging.getLogger(__name__)

PRICE_DOWN = "price_down"
PRICE_UP = "price_up"
BELOW_ALERT = "below_alert"
OUT_OF_STOCK = "out_of_stock"
BACK_IN_STOCK = "back_in_stock"
NEW_LOWEST = "new_lowest"

EVENT_LABELS = {
    PRICE_DOWN: "値下げ",
    PRICE_UP: "値上げ",
    BELOW_ALERT: "アラート価格割れ",
    OUT_OF_STOCK: "取得不可/在庫切れ",
    BACK_IN_STOCK: "販売再開",
    NEW_LOWEST: "最安値更新",
}


@dataclass
class Event:
    kind: str
    listing: Listing | None
    product: str
    old: int | None
    new: int | None
    note: str = ""

    @property
    def label(self) -> str:
        return EVENT_LABELS.get(self.kind, self.kind)

    def describe(self) -> str:
        where = f"{self.listing.site} / {self.listing.shop}" if self.listing else "全店舗"
        fmt = lambda v: "-" if v is None else f"¥{v:,}"
        diff = ""
        if self.old is not None and self.new is not None:
            d = self.new - self.old
            diff = f" ({'+' if d > 0 else ''}{d:,})"
        text = f"[{self.label}] {self.product} | {where} | {fmt(self.old)} → {fmt(self.new)}{diff}"
        if self.note:
            text += f" | {self.note}"
        if self.listing:
            text += f"\n  {self.listing.url}"
        return text


def check_listing(fetcher: Fetcher, listing: Listing) -> PriceResult:
    parser = get_parser(listing.url)
    try:
        use_browser = fetcher.use_browser or (fetcher.auto_browser and parser.config.prefers_browser)
        html = fetcher.get(listing.url, browser=use_browser)
    except FetchError as exc:
        return PriceResult(error=f"fetch_error: {exc}")
    try:
        result = parser.parse(html, listing)
    except Exception as exc:  # パーサの想定外エラーで巡回全体を止めない
        log.exception("parse failed: %s", listing.url)
        return PriceResult(error=f"parse_error: {exc}")
    if listing.point_rate is not None and result.price is not None:
        result.points = points_from_rate(result.price, listing.point_rate)
    return result


def detect_events(db: Database, run_id: int, listing: Listing, result: PriceResult) -> list[Event]:
    events: list[Event] = []
    prev = db.previous_snapshot(listing.id, run_id)
    prev_ok = db.previous_snapshot(listing.id, run_id, ok_only=True)
    new = result.effective

    if new is not None and prev_ok is not None:
        old = prev_ok["effective"]
        if new < old:
            events.append(Event(PRICE_DOWN, listing, listing.product, old, new))
        elif new > old:
            events.append(Event(PRICE_UP, listing, listing.product, old, new))

    if new is None and prev is not None and prev["effective"] is not None:
        events.append(Event(OUT_OF_STOCK, listing, listing.product, prev["effective"], None, result.error or ""))
    if new is not None and prev is not None and prev["effective"] is None:
        events.append(Event(BACK_IN_STOCK, listing, listing.product, None, new))

    # アラート価格: 新たに下回ったときだけ通知（毎回通知しない）
    for n, threshold in ((1, listing.alert_price1), (2, listing.alert_price2)):
        if threshold is None or new is None:
            continue
        was_below = prev_ok is not None and prev_ok["effective"] < threshold
        if new < threshold and not was_below:
            events.append(Event(BELOW_ALERT, listing, listing.product, threshold, new, f"アラート価格{n} ¥{threshold:,}"))
    return events


def run_check(
    db: Database,
    fetcher: Fetcher | None = None,
    listings: list[Listing] | None = None,
    notify: Callable[[list[Event]], None] | None = None,
    progress: Callable[[int, int, Listing, PriceResult], None] | None = None,
) -> tuple[int, list[Event]]:
    fetcher = fetcher or Fetcher()
    fetcher.clear_cache()
    targets = listings if listings is not None else db.listings(active_only=True)
    run_id = db.start_run()
    events: list[Event] = []
    current: dict[str, list[int]] = {}
    previous: dict[str, list[int]] = {}

    for i, listing in enumerate(targets, 1):
        result = check_listing(fetcher, listing)
        events += detect_events(db, run_id, listing, result)
        prev_ok = db.previous_snapshot(listing.id, run_id, ok_only=True)
        if prev_ok is not None:
            previous.setdefault(listing.product, []).append(prev_ok["effective"])
        db.add_snapshot(run_id, listing.id, result)
        if result.effective is not None:
            current.setdefault(listing.product, []).append(result.effective)
        if progress:
            progress(i, len(targets), listing, result)

    events += lowest_price_events(current, previous)
    db.finish_run(run_id)
    if notify and events:
        try:
            notify(events)
        except Exception:
            log.exception("notification failed")
    return run_id, events


def lowest_price_events(current: dict[str, list[int]], previous: dict[str, list[int]]) -> list[Event]:
    """商品ごとの全店舗最安値が、各店舗の直近の取得済み価格の最安より下がったら通知。

    一時的に取得できなかった店舗が戻っただけで「最安値更新」にならないよう、
    前回の巡回ではなく店舗ごとの最後に取れた価格と比べる。
    """
    events = []
    for product, values in current.items():
        if not previous.get(product):
            continue
        old_min, new_min = min(previous[product]), min(values)
        if new_min < old_min:
            events.append(Event(NEW_LOWEST, None, product, old_min, new_min))
    return events


def summarize(events: list[Event], at=None) -> str:
    at = at or now_jst()
    head = f"【価格監視】{at:%Y/%m/%d %H:%M} 変動 {len(events)} 件"
    order = [NEW_LOWEST, BELOW_ALERT, PRICE_DOWN, PRICE_UP, OUT_OF_STOCK, BACK_IN_STOCK]
    body = "\n".join(e.describe() for e in sorted(events, key=lambda e: order.index(e.kind)))
    return f"{head}\n{body}"
