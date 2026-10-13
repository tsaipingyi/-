"""SQLite 保存。監視対象（listings）・実行（runs）・取得結果（snapshots）。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .models import JST, Listing, PriceResult, now_jst

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    shop TEXT NOT NULL DEFAULT '',
    product TEXT NOT NULL,
    url TEXT NOT NULL,
    alert_price1 INTEGER,
    alert_price2 INTEGER,
    point_rate REAL,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(url, shop)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    checked_at TEXT NOT NULL,
    price INTEGER,
    points INTEGER NOT NULL DEFAULT 0,
    effective INTEGER,
    in_stock INTEGER,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_listing ON snapshots(listing_id, run_id);
CREATE INDEX IF NOT EXISTS idx_snap_run ON snapshots(run_id);
"""


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=JST)


def _row_to_listing(r: sqlite3.Row) -> Listing:
    return Listing(
        id=r["id"],
        site=r["site"],
        shop=r["shop"],
        product=r["product"],
        url=r["url"],
        alert_price1=r["alert_price1"],
        alert_price2=r["alert_price2"],
        point_rate=r["point_rate"],
        active=bool(r["active"]),
    )


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ---- listings -------------------------------------------------------
    def upsert_listing(self, l: Listing) -> int:
        with self.tx() as c:
            row = c.execute("SELECT id FROM listings WHERE url=? AND shop=?", (l.url, l.shop)).fetchone()
            if row:
                c.execute(
                    "UPDATE listings SET site=?, product=?, alert_price1=?, alert_price2=?, point_rate=?, active=? "
                    "WHERE id=?",
                    (l.site, l.product, l.alert_price1, l.alert_price2, l.point_rate, int(l.active), row["id"]),
                )
                return row["id"]
            order = c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM listings").fetchone()[0]
            cur = c.execute(
                "INSERT INTO listings (site, shop, product, url, alert_price1, alert_price2, point_rate, active, "
                "sort_order, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (l.site, l.shop, l.product, l.url, l.alert_price1, l.alert_price2, l.point_rate, int(l.active),
                 order, _ts(now_jst())),
            )
            return cur.lastrowid

    def listings(self, active_only: bool = False, product: str | None = None) -> list[Listing]:
        sql = "SELECT * FROM listings WHERE 1=1"
        args: list = []
        if active_only:
            sql += " AND active=1"
        if product:
            sql += " AND product=?"
            args.append(product)
        sql += " ORDER BY sort_order, id"
        return [_row_to_listing(r) for r in self.conn.execute(sql, args)]

    def get_listing(self, listing_id: int) -> Listing | None:
        r = self.conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        return _row_to_listing(r) if r else None

    def set_active(self, listing_id: int, active: bool) -> None:
        with self.tx() as c:
            c.execute("UPDATE listings SET active=? WHERE id=?", (int(active), listing_id))

    def delete_listing(self, listing_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM snapshots WHERE listing_id=?", (listing_id,))
            c.execute("DELETE FROM listings WHERE id=?", (listing_id,))

    def products(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT DISTINCT product FROM listings ORDER BY product")]

    # ---- runs / snapshots ----------------------------------------------
    def start_run(self, at: datetime | None = None) -> int:
        with self.tx() as c:
            return c.execute("INSERT INTO runs (started_at) VALUES (?)", (_ts(at or now_jst()),)).lastrowid

    def finish_run(self, run_id: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET finished_at=? WHERE id=?", (_ts(now_jst()), run_id))

    def add_snapshot(self, run_id: int, listing_id: int, result: PriceResult, at: datetime | None = None) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO snapshots (run_id, listing_id, checked_at, price, points, effective, in_stock, error) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (run_id, listing_id, _ts(at or now_jst()), result.price, result.points or 0, result.effective,
                 None if result.in_stock is None else int(result.in_stock), result.error),
            )

    def runs(self, limit: int | None = None) -> list[dict]:
        """新しい順に取得して古い順で返す（表の左→右が時系列）。"""
        sql = "SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = [dict(r) for r in self.conn.execute(sql)]
        for r in rows:
            r["started_at"] = parse_ts(r["started_at"])
        return list(reversed(rows))

    def snapshots_for_runs(self, run_ids: list[int]) -> dict[tuple[int, int], dict]:
        if not run_ids:
            return {}
        q = ",".join("?" * len(run_ids))
        out = {}
        for r in self.conn.execute(f"SELECT * FROM snapshots WHERE run_id IN ({q})", run_ids):
            out[(r["listing_id"], r["run_id"])] = dict(r)
        return out

    def previous_snapshot(self, listing_id: int, before_run_id: int, ok_only: bool = False) -> dict | None:
        sql = "SELECT * FROM snapshots WHERE listing_id=? AND run_id<?"
        if ok_only:
            sql += " AND effective IS NOT NULL"
        sql += " ORDER BY run_id DESC LIMIT 1"
        r = self.conn.execute(sql, (listing_id, before_run_id)).fetchone()
        return dict(r) if r else None

    def history(self, listing_id: int, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM snapshots WHERE listing_id=? ORDER BY run_id DESC LIMIT ?", (listing_id, limit)
        )
        return [dict(r) for r in rows]
