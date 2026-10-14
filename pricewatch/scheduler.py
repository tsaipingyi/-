"""定期巡回。Web 画面からの「今すぐ確認」と重ならないようロックをかける。"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from .config import Settings
from .db import Database
from .fetch import Fetcher
from .monitor import run_check
from .notify import Notifier

log = logging.getLogger(__name__)


class Checker:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.notifier = Notifier(settings)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.status = "待機中"

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def make_fetcher(self) -> Fetcher:
        s = self.settings
        return Fetcher(delay=s.request_delay, use_browser=s.use_browser, auto_browser=s.auto_browser)

    def check_now(self, listings=None) -> bool:
        """巡回を1回実行。すでに実行中なら False。"""
        if not self._lock.acquire(blocking=False):
            return False
        fetcher = self.make_fetcher()
        try:
            def progress(i, n, listing, result):
                self.status = f"確認中 {i}/{n}: {listing.site} {listing.shop}"

            run_id, events = run_check(self.db, fetcher, listings=listings, notify=self.notifier, progress=progress)
            self.status = f"完了 (run #{run_id}, 変動 {len(events)} 件)"
            log.info(self.status)
            self._backup()
            return True
        except Exception:
            log.exception("巡回に失敗しました")
            self.status = "エラー（ログを確認してください）"
            return True
        finally:
            fetcher.close()
            self._lock.release()

    def _backup(self) -> None:
        if self.db.path == ":memory:":
            return
        try:
            dest = self.db.backup(Path(self.db.path).parent / "backups")
            if dest:
                log.info("バックアップしました: %s", dest)
        except Exception:
            log.exception("バックアップに失敗しました")

    def check_in_background(self) -> bool:
        if self.running:
            return False
        threading.Thread(target=self.check_now, daemon=True).start()
        return True

    def loop(self, interval_minutes: int, run_immediately: bool = True) -> None:
        if run_immediately:
            self.check_now()
        while not self._stop.wait(interval_minutes * 60):
            self.check_now()

    def start_background_loop(self, interval_minutes: int) -> threading.Thread:
        t = threading.Thread(target=self.loop, args=(interval_minutes,), daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()
