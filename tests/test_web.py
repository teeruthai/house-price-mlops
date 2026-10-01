from fastapi.testclient import TestClient

from src.web import app


def test_index_page():
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "ทำนายราคาบ้าน" in r.text