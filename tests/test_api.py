from fastapi.testclient import TestClient
from app import create_app

def test_demo_seed_and_summary(tmp_path):
    with TestClient(create_app(str(tmp_path / "test.db"))) as client:
        s = client.get("/api/summary").json()
        assert s["total"] == 12
        assert s["counts"]["won"] == 2
        assert s["pipeline_amount"] > 0

def test_lead_lifecycle(tmp_path):
    with TestClient(create_app(str(tmp_path / "test.db"))) as client:
        payload = {"company":"Example Ltd", "contact":"Test User", "service":"Telegram bot", "amount":210000}
        r = client.post("/api/leads", json=payload)
        assert r.status_code == 201
        key = r.json()["id"]
        assert client.patch(f"/api/leads/{key}", json={"stage":"won"}).json()["stage"] == "won"
        assert client.get("/api/leads?stage=won").status_code == 200
        assert client.get("/api/export.csv").content.startswith(b"\xef\xbb\xbf")
        assert client.delete(f"/api/leads/{key}").status_code == 204
        assert client.patch(f"/api/leads/{key}", json={"stage":"new"}).status_code == 404

def test_validation_and_search(tmp_path):
    with TestClient(create_app(str(tmp_path / "test.db"))) as client:
        assert client.post("/api/leads", json={"company":"x","contact":"A", "service":"s", "amount":-1}).status_code == 422
        assert client.get("/api/leads?stage=bogus").status_code == 400
        assert any(x["company"] == "Northstar Studio" for x in client.get("/api/leads?q=Northstar").json())
