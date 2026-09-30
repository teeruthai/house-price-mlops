from fastapi.testclient import TestClient
from src.app import app

VALID = {"area_sqm": 120, "bedrooms": 3, "bathrooms": 2, "age_years": 5, "location": "suburb"}


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200 and r.json()["model_loaded"] is True


def test_predict_returns_positive_price():
    with TestClient(app) as c:
        r = c.post("/predict", json=VALID)
        assert r.status_code == 200
        assert r.json()["predicted_price"] > 0


def test_city_center_more_expensive_than_rural():
    with TestClient(app) as c:
        p = lambda loc: c.post("/predict", json={**VALID, "location": loc}).json()["predicted_price"]
        assert p("city_center") > p("rural")


def test_invalid_input_rejected():
    with TestClient(app) as c:
        assert c.post("/predict", json={**VALID, "location": "moon"}).status_code == 422
        assert c.post("/predict", json={**VALID, "area_sqm": -5}).status_code == 422