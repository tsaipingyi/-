"""HTTP 取得。ドメインごとの間隔制御・リトライ・文字コード判定・同一URLのキャッシュを行う。"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.6 Safari/605.1.15",
]

_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([A-Za-z0-9_\-]+)""", re.I)


class FetchError(Exception):
    pass


def decode_html(content: bytes, header_encoding: str | None) -> str:
    """HTTP ヘッダ → meta charset → 推定 の順で文字コードを決める（価格.com 等の Shift_JIS 対策）。"""
    candidates = []
    if header_encoding and header_encoding.lower() not in ("iso-8859-1", "latin-1"):
        candidates.append(header_encoding)
    m = _META_CHARSET.search(content[:4096])
    if m:
        candidates.append(m.group(1).decode("ascii", "ignore"))
    candidates += ["utf-8", "cp932", "euc-jp"]
    for enc in candidates:
        enc = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932"}.get(enc.lower(), enc)
        try:
            return content.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(
        self,
        delay: float = 3.0,
        timeout: float = 20.0,
        retries: int = 2,
        use_browser: bool = False,
        auto_browser: bool = False,
        session: requests.Session | None = None,
    ):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        # use_browser: 全サイトをブラウザで取得 / auto_browser: Amazon など対策の強いサイトだけブラウザで取得
        self.use_browser = use_browser
        self.auto_browser = auto_browser
        self.session = session or requests.Session()
        self._last_hit: dict[str, float] = {}
        self._cache: dict[str, str] = {}
        self._errors: dict[str, FetchError] = {}
        self._lock = threading.Lock()
        self._browser = None

    def clear_cache(self) -> None:
        self._cache.clear()
        self._errors.clear()

    def _wait_for_domain(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        with self._lock:
            last = self._last_hit.get(host)
            if last is not None:
                wait = self.delay + random.uniform(0, self.delay * 0.3) - (time.monotonic() - last)
                if wait > 0:
                    time.sleep(wait)
            self._last_hit[host] = time.monotonic()

    def get(self, url: str, browser: bool | None = None) -> str:
        """同一実行中は同じ URL を再取得しない（価格.com のように1ページに複数店舗がある場合）。"""
        if url in self._cache:
            return self._cache[url]
        if url in self._errors:
            raise self._errors[url]
        use_browser = self.use_browser if browser is None else browser
        try:
            html = self._get_browser(url) if use_browser else self._get_http(url)
        except FetchError as exc:
            self._errors[url] = exc
            raise
        self._cache[url] = html
        return html

    def _get_http(self, url: str) -> str:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.5",
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait_for_domain(url)
            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
            else:
                if resp.status_code == 200:
                    return decode_html(resp.content, resp.encoding)
                if resp.status_code in (404, 410):
                    raise FetchError(f"HTTP {resp.status_code}")
                last_exc = FetchError(f"HTTP {resp.status_code}")
            time.sleep(2 ** attempt)
        raise FetchError(str(last_exc))

    def _get_browser(self, url: str) -> str:
        """Playwright（任意）で JS 描画後の HTML を取得。Amazon 等ボット対策の強いサイト向け。"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - 任意依存
            raise FetchError("playwright が未インストールです: pip install playwright") from exc
        self._wait_for_domain(url)
        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
        page = self._browser.new_page(locale="ja-JP", user_agent=random.choice(USER_AGENTS))
        try:
            page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            return page.content()
        except Exception as exc:
            raise FetchError(str(exc)) from exc
        finally:
            page.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._pw.stop()
            self._browser = None
