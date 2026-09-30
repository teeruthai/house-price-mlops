"""ขั้นที่ 3: FastAPI สำหรับ serve โมเดล"""
import json
import os
import time
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_DIR = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parent.parent / "model"))
LOG_FILE = Path(os.getenv("PRED_LOG", "logs/predictions.jsonl"))

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


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": state["model"] is not None,
            "model_version": state["meta"].get("version")}


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
    try:  # log สำหรับ monitoring
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), "input": f.model_dump(),
                                 "prediction": price, "latency_ms": latency}) + "\n")
    except OSError:
        pass
    return {"predicted_price": round(price, -3), "currency": "THB",
            "model_name": state["meta"].get("model_name"),
            "model_version": state["meta"].get("version")}


@app.get("/metrics")
def metrics():
    n = state["n_requests"]
    return {"requests": n, "avg_latency_ms": (state["total_latency_ms"] / n) if n else 0.0}