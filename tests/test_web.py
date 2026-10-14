from pricewatch.config import load_settings
from pricewatch.db import Database
from pricewatch.models import Listing, PriceResult
from pricewatch.scheduler import Checker
from pricewatch.web.app import create_app


def test_pages_render():
    db = Database(":memory:")
    lid = db.upsert_listing(Listing("楽天市場", "店A", "FIT 4", "https://item.rakuten.co.jp/a/1/", alert_price2=21582))
    for price in (19010, 18800):
        run = db.start_run()
        db.add_snapshot(run, lid, PriceResult(price=price, points=100))
        db.finish_run(run)

    app = create_app(db, Checker(db, load_settings()))
    client = app.test_client()
    html = client.get("/").get_data(as_text=True)
    assert "商品価格-ポイント" in html and "18,700" in html and "down" in html
    assert client.get("/listings").status_code == 200
    assert "18,910" in client.get(f"/listings/{lid}").get_data(as_text=True)
    resp = client.get("/export.xlsx")
    assert resp.status_code == 200 and resp.data[:2] == b"PK"

    client.post("/listings", data={"url": "https://www.sofmap.com/x", "product": "FIT 4"})
    assert [l.site for l in db.listings()] == ["楽天市場", "ソフマップ"]


def test_password_required():
    db = Database(":memory:")
    client = create_app(db, Checker(db, load_settings()), password="secret").test_client()
    assert client.get("/").status_code == 401
    ok = client.get("/", headers={"Authorization": "Basic " + __import__("base64").b64encode(b"any:secret").decode()})
    assert ok.status_code == 200
    bad = client.get("/", headers={"Authorization": "Basic " + __import__("base64").b64encode(b"any:nope").decode()})
    assert bad.status_code == 401


def test_import_upload(tmp_path):
    import io

    db = Database(":memory:")
    client = create_app(db, Checker(db, load_settings()), password="").test_client()
    csv = "販売商品URL,店舗,商品名\nhttps://www.sofmap.com/x,ソフマップ,FIT 4\n".encode("cp932")
    client.post("/listings/import", data={"file": (io.BytesIO(csv), "list.csv")},
                content_type="multipart/form-data")
    assert [(l.shop, l.product) for l in db.listings()] == [("ソフマップ", "FIT 4")]


def test_daily_backup(tmp_path):
    db = Database(tmp_path / "pw.db")
    db.upsert_listing(Listing("楽天市場", "店A", "FIT 4", "https://item.rakuten.co.jp/a/1/"))
    first = db.backup(tmp_path / "backups")
    assert first and first.exists()
    assert db.backup(tmp_path / "backups") is None  # 同じ日は1回だけ
    assert len(Database(first).listings()) == 1
