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
