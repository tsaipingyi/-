"""Web 画面: 価格推移表・監視対象の管理・Excel ダウンロード。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from ..db import Database
from ..importer import import_file
from ..models import Listing
from ..parsers import site_name_for_url
from ..parsers.base import parse_yen
from ..report import build_matrix, export_excel
from ..scheduler import Checker


def _int_or_none(v: str | None) -> int | None:
    return parse_yen(v) if v and v.strip() else None


def create_app(db: Database, checker: Checker) -> Flask:
    app = Flask(__name__)
    app.secret_key = "pricewatch-local"  # flash メッセージ用（ローカル利用前提）

    @app.template_filter("yen")
    def yen(v):
        return "" if v is None else f"{v:,}"

    @app.get("/")
    def index():
        product = request.args.get("product") or None
        runs = request.args.get("runs", 12, type=int)
        matrix = build_matrix(db, limit=runs, product=product)
        return render_template("index.html", m=matrix, products=db.products(), product=product, runs=runs,
                               status=checker.status, running=checker.running)

    @app.get("/listings")
    def listings():
        return render_template("listings.html", listings=db.listings(), status=checker.status,
                               running=checker.running)

    @app.post("/listings")
    def add_listing():
        f = request.form
        url = f.get("url", "").strip()
        if not url.startswith("http"):
            flash("URL を入力してください")
            return redirect(url_for("listings"))
        site = f.get("site", "").strip() or site_name_for_url(url)
        rate = f.get("point_rate", "").strip()
        db.upsert_listing(Listing(
            site=site, shop=f.get("shop", "").strip() or site, product=f.get("product", "").strip() or "(未設定)",
            url=url, alert_price1=_int_or_none(f.get("alert_price1")), alert_price2=_int_or_none(f.get("alert_price2")),
            point_rate=float(rate) if rate else None,
        ))
        flash("登録しました")
        return redirect(url_for("listings"))

    @app.post("/listings/import")
    def import_listings():
        file = request.files.get("file")
        if not file or not file.filename:
            flash("ファイルを選択してください")
            return redirect(url_for("listings"))
        suffix = Path(file.filename).suffix or ".csv"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            file.save(tmp.name)
        try:
            n = import_file(db, tmp.name)
            flash(f"{n} 件を登録/更新しました")
        except ValueError as exc:
            flash(str(exc))
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        return redirect(url_for("listings"))

    @app.post("/listings/<int:lid>/toggle")
    def toggle_listing(lid: int):
        l = db.get_listing(lid) or abort(404)
        db.set_active(lid, not l.active)
        return redirect(url_for("listings"))

    @app.post("/listings/<int:lid>/delete")
    def delete_listing(lid: int):
        db.delete_listing(lid)
        flash("削除しました")
        return redirect(url_for("listings"))

    @app.get("/listings/<int:lid>")
    def history(lid: int):
        l = db.get_listing(lid) or abort(404)
        return render_template("history.html", l=l, rows=db.history(lid), status=checker.status,
                               running=checker.running)

    @app.post("/check")
    def check():
        if checker.check_in_background():
            flash("価格確認を開始しました。完了まで数分かかることがあります。")
        else:
            flash("すでに確認中です")
        return redirect(request.referrer or url_for("index"))

    @app.get("/status")
    def status():
        return jsonify(status=checker.status, running=checker.running)

    @app.get("/export.xlsx")
    def export():
        product = request.args.get("product") or None
        runs = request.args.get("runs", 30, type=int)
        tmp = Path(tempfile.mkdtemp()) / "価格推移.xlsx"
        export_excel(db, tmp, limit=runs, product=product)
        return send_file(tmp, as_attachment=True, download_name="価格推移.xlsx")

    return app
