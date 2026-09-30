"""ขั้นที่ 1-2: Tracking + Model Registry
- สร้างข้อมูลจำลอง, ฝึกโมเดล 2 แบบ, log ลง MLflow
- เลือกโมเดลที่ RMSE ต่ำสุด -> register เป็น house-price-model (version 1)
- export โมเดลเป็นไฟล์ model/model.joblib ให้ API/Docker ใช้งาน
"""
import json
import argparse
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

MODEL_NAME = "house-price-model"
EXPERIMENT = "house-price-prediction"
NUM_COLS = ["area_sqm", "bedrooms", "bathrooms", "age_years"]
CAT_COLS = ["location"]
LOCATIONS = ["city_center", "suburb", "rural"]
ROOT = Path(__file__).resolve().parent.parent



def make_data(n: int = 3000, seed: int = 42) -> pd.DataFrame:
    """ข้อมูลจำลองราคาบ้าน (บาท) - มี interaction ไม่เป็นเส้นตรงล้วน"""
    rng = np.random.default_rng(seed)
    loc = rng.choice(LOCATIONS, n, p=[0.3, 0.45, 0.25])
    area = rng.normal(140, 50, n).clip(35, 400)
    bedrooms = rng.integers(1, 6, n)
    bathrooms = rng.integers(1, 5, n)
    age = rng.integers(0, 40, n)
    per_sqm = pd.Series(loc).map({"city_center": 85000, "suburb": 48000, "rural": 26000}).values
    price = (area * per_sqm * (1 - 0.008 * age)
             + bedrooms * 250_000 * (loc == "city_center") + bedrooms * 120_000
             + bathrooms * 200_000)
    price *= rng.normal(1, 0.05, n)
    return pd.DataFrame({"area_sqm": area.round(1), "bedrooms": bedrooms, "bathrooms": bathrooms,
                         "age_years": age, "location": loc, "price": price.round(-3)})


def build_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUM_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
    ])
    return Pipeline([("prep", pre), ("model", estimator)])


def main(n_samples: int = 3000, tracking_uri: str | None = None):
    mlflow.set_tracking_uri(tracking_uri or f"sqlite:///{ROOT / 'mlflow.db'}")
    mlflow.set_experiment(EXPERIMENT)

    df = make_data(n_samples)
    X, y = df[NUM_COLS + CAT_COLS], df["price"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)


    candidates = {
        "linear_regression": (LinearRegression(), {}),
        "random_forest": (RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1),
                          {"n_estimators": 200, "max_depth": 12}),
    }

    results = []
    for name, (est, params) in candidates.items():
        pipe = build_pipeline(est)
        with mlflow.start_run(run_name=name) as run:
            pipe.fit(X_tr, y_tr)
            pred = pipe.predict(X_te)
            rmse = float(np.sqrt(mean_squared_error(y_te, pred)))
            metrics = {"rmse": rmse, "mae": float(mean_absolute_error(y_te, pred)),
                       "r2": float(r2_score(y_te, pred))}
            mlflow.log_param("algorithm", name)
            mlflow.log_params(params)
            mlflow.log_param("n_train", len(X_tr))
            mlflow.log_metrics(metrics)
            sig = infer_signature(X_tr, pipe.predict(X_tr.head(5)))
            # โมเดลเราเทรนเอง จึงใช้ cloudpickle ได้ (MLflow เวอร์ชันใหม่ใช้ skops เป็นค่าเริ่มต้น)
            mlflow.sklearn.log_model(pipe, "model", signature=sig, input_example=X_tr.head(3),
                                     serialization_format="cloudpickle")
            results.append({"name": name, "run_id": run.info.run_id, "rmse": rmse, "pipe": pipe})
            print(f"[{name}] RMSE={rmse:,.0f}  MAE={metrics['mae']:,.0f}  R2={metrics['r2']:.4f}")

    best = min(results, key=lambda r: r["rmse"])
    print(f"\n>>> Best model: {best['name']} (RMSE={best['rmse']:,.0f})")

    # ---- Model Registry ----
    mv = mlflow.register_model(f"runs:/{best['run_id']}/model", MODEL_NAME)

    client = MlflowClient()
    client.set_registered_model_alias(MODEL_NAME, "production", mv.version)
    client.set_model_version_tag(MODEL_NAME, mv.version, "stage", "Production")
    client.set_model_version_tag(MODEL_NAME, mv.version, "algorithm", best["name"])
    print(f">>> Registered {MODEL_NAME}:v{mv.version} (alias=production)")

    # ---- Export ให้ API ใช้ ----
    out = ROOT / "model"
    out.mkdir(exist_ok=True)
    joblib.dump(best["pipe"], out / "model.joblib")
    (out / "metadata.json").write_text(json.dumps({
        "model_name": MODEL_NAME, "version": str(mv.version),
        "algorithm": best["name"], "rmse": best["rmse"]}, indent=2))
    # baseline ไว้ใช้ตรวจ drift
    df[NUM_COLS].describe().loc[["mean", "std"]].to_json(out / "baseline_stats.json")
    return best["name"], best["rmse"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-samples", type=int, default=3000)
    main(ap.parse_args().n_samples)