"""ขั้นที่ 3: FastAPI สำหรับ serve โมเดล"""
import json
import os
import time
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

MODEL_DIR = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parent.parent / "model"))
LOG_FILE = Path(os.getenv("PRED_LOG", "logs/predictions.jsonl"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# เชื่อมต่อ Firebase Firestore (อ่านคีย์จาก env var FIREBASE_CREDENTIALS)
db = None
_cred_json = os.getenv("FIREBASE_CREDENTIALS")
if _cred_json:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        firebase_admin.initialize_app(credentials.Certificate(json.loads(_cred_json)))
        db = firestore.client()
    except Exception as e:
        print("FIREBASE INIT ERROR:", e)

app = FastAPI(title="House Price Prediction API", version="1.0.0")
state = {"model": None, "meta": {}, "n_requests": 0, "total_latency_ms": 0.0}


class HouseFeatures(BaseModel):
    area_sqm: float = Field(..., gt=10, lt=2000, description="พื้นที่ใช้สอย (ตร.ม.)")
    bedrooms: int = Field(..., ge=1, le=10)
    bathrooms: int = Field(1, ge=1, le=10)
    age_years: int = Field(0, ge=0, le=100)
    location: Literal["city_center", "suburb", "rural"]


@app.on_event("startup")
def load_model():
    state["model"] = joblib.load(MODEL_DIR / "model.joblib")
    state["meta"] = json.loads((MODEL_DIR / "metadata.json").read_text())


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": state["model"] is not None,
            "model_version": state["meta"].get("version"),
            "firebase_connected": db is not None}


@app.post("/predict")
def predict(f: HouseFeatures):
    if state["model"] is None:
        raise HTTPException(503, "model not loaded")
    t0 = time.perf_counter()
    df = pd.DataFrame([f.model_dump()])
    price = float(state["model"].predict(df)[0])
    latency = (time.perf_counter() - t0) * 1000
    state["n_requests"] += 1
    state["total_latency_ms"] += latency

    # log ลงไฟล์ในเครื่อง (สำหรับ monitoring)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), "input": f.model_dump(),
                                 "prediction": price, "latency_ms": latency}) + "\n")
    except OSError:
        pass

    # log ขึ้น Firebase (cloud)
    if db is not None:
        try:
            db.collection("prediction_logs").add({
                "created_at": firestore.SERVER_TIMESTAMP,
                "area_sqm": f.area_sqm,
                "bedrooms": f.bedrooms,
                "bathrooms": f.bathrooms,
                "age_years": f.age_years,
                "location": f.location,
                "predicted_price": price,
                "latency_ms": latency,
                "model_version": state["meta"].get("version"),
            })
        except Exception as e:
            print("FIREBASE LOG ERROR:", e)

    return {"predicted_price": round(price, -3), "currency": "THB",
            "model_name": state["meta"].get("model_name"),
            "model_version": state["meta"].get("version")}


@app.get("/metrics")
def metrics():
    n = state["n_requests"]
    return {"requests": n, "avg_latency_ms": (state["total_latency_ms"] / n) if n else 0.0}