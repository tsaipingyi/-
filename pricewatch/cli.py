"""コマンドライン: pricewatch <command>"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_settings
from .db import Database
from .fetch import Fetcher, FetchError
from .importer import import_file
from .models import Listing
from .monitor import check_listing, run_check, summarize
from .notify import Notifier
from .parsers import get_parser, site_name_for_url
from .report import export_excel
from .scheduler import Checker


def _yen(v) -> str:
    return "-" if v is None else f"¥{v:,}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pricewatch", description="日本市場向け 商品価格監視")
    ap.add_argument("--db", help="SQLite ファイル（既定: data/pricewatch.db）")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import", help="CSV / Excel から監視対象を一括登録")
    p.add_argument("file")

    p = sub.add_parser("add", help="監視対象を1件追加")
    p.add_argument("url")
    p.add_argument("--product", required=True)
    p.add_argument("--shop", default="")
    p.add_argument("--site", default="")
    p.add_argument("--alert1", type=int)
    p.add_argument("--alert2", type=int)
    p.add_argument("--point-rate", type=float, help="ポイント還元率(%%)を固定で指定")

    sub.add_parser("list", help="監視対象と最新価格を表示")

    p = sub.add_parser("check", help="今すぐ全件の価格を確認")
    p.add_argument("--no-notify", action="store_true")

    p = sub.add_parser("run", help="一定間隔で確認し続ける")
    p.add_argument("--interval", type=int, help="分（既定: PRICEWATCH_INTERVAL または 60）")

    p = sub.add_parser("export", help="Excel に書き出し（今のスプレッドシートと同じ形式）")
    p.add_argument("file", nargs="?", default="価格推移.xlsx")
    p.add_argument("--runs", type=int, default=30, help="直近何回分を列にするか")
    p.add_argument("--product")

    p = sub.add_parser("serve", help="Web 画面を起動（定期確認も同時に実行）")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--interval", type=int, help="定期確認の間隔（分）。0 で無効")

    p = sub.add_parser("test-url", help="1つの URL を取得・解析して結果を表示（セレクタ調整用）")
    p.add_argument("url")
    p.add_argument("--shop", default="", help="価格.com の場合は店舗名")
    p.add_argument("--html", help="取得の代わりに保存済み HTML ファイルを解析")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()
    if args.db:
        settings.db_path = args.db

    if args.cmd == "test-url":
        return _test_url(args, settings)

    db = Database(settings.db_path)

    if args.cmd == "import":
        n = import_file(db, args.file)
        print(f"{n} 件を登録/更新しました")
    elif args.cmd == "add":
        lid = db.upsert_listing(Listing(
            site=args.site or site_name_for_url(args.url),
            shop=args.shop or args.site or site_name_for_url(args.url),
            product=args.product, url=args.url,
            alert_price1=args.alert1, alert_price2=args.alert2, point_rate=args.point_rate,
        ))
        print(f"登録しました (id={lid})")
    elif args.cmd == "list":
        for l in db.listings():
            h = db.history(l.id, limit=1)
            latest = h[0]["effective"] if h else None
            flag = "" if l.active else " [停止中]"
            print(f"{l.id:>4} {l.site:<14} {l.shop:<22} {l.product:<16} {_yen(latest):>10}{flag}")
    elif args.cmd == "check":
        fetcher = Checker(db, settings).make_fetcher()

        def progress(i, n, listing, result):
            state = _yen(result.effective) if result.ok else result.error
            print(f"[{i}/{n}] {listing.site} / {listing.shop}: {state}", flush=True)

        try:
            _, events = run_check(db, fetcher, notify=None if args.no_notify else Notifier(settings),
                                  progress=progress)
        finally:
            fetcher.close()
        print(summarize(events) if events else "変動はありません")
    elif args.cmd == "run":
        interval = args.interval or settings.interval_minutes
        print(f"{interval} 分ごとに確認します（Ctrl+C で停止）")
        try:
            Checker(db, settings).loop(interval)
        except KeyboardInterrupt:
            pass
    elif args.cmd == "export":
        path = export_excel(db, args.file, limit=args.runs, product=args.product)
        print(f"書き出しました: {path}")
    elif args.cmd == "serve":
        from .web.app import create_app

        checker = Checker(db, settings)
        interval = settings.interval_minutes if args.interval is None else args.interval
        if interval > 0:
            checker.start_background_loop(interval)
            print(f"{interval} 分ごとに自動確認します")
        create_app(db, checker).run(host=args.host, port=args.port, threaded=True)
    return 0


def _test_url(args, settings) -> int:
    parser = get_parser(args.url)
    listing = Listing(site=parser.name, shop=args.shop, product="test", url=args.url)
    print(f"サイト判定: {parser.name}")
    if args.html:
        with open(args.html, encoding="utf-8", errors="replace") as f:
            result = parser.parse(f.read(), listing)
    else:
        fetcher = Fetcher(delay=0, use_browser=settings.use_browser, auto_browser=settings.auto_browser)
        try:
            result = check_listing(fetcher, listing)
        except FetchError as exc:
            print(f"取得失敗: {exc}")
            return 1
        finally:
            fetcher.close()
    print(f"価格: {_yen(result.price)}  ポイント: {result.points}  価格-ポイント: {_yen(result.effective)}")
    print(f"在庫: {result.in_stock}  エラー: {result.error}  取得元: {result.raw}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
