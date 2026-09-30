"""จำลองการส่ง request เข้า API ทำนายราคาบ้าน เพื่อตรวจสอบประสิทธิภาพ (Model Monitoring)

วิธีใช้:
    pip install requests
    python scripts/simulate_traffic.py --url http://127.0.0.1:8000/predict --n 200
"""
import argparse
import random
import statistics
import time

import requests

LOCATIONS = ["city_center", "suburb", "rural"] # แก้ให้ตรงกับค่าที่โมเดลรองรับ


def make_payload():
    return {
        "area_sqm": round(random.uniform(30, 400), 1),
        "bedrooms": random.randint(1, 6),
        "bathrooms": random.randint(1, 4),
        "age_years": random.randint(0, 50),
        "location": random.choice(LOCATIONS),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/predict")
    p.add_argument("--n", type=int, default=200)
    args = p.parse_args()

    latencies, preds, errors = [], [], 0

    for _ in range(args.n):
        payload = make_payload()
        start = time.perf_counter()
        try:
            r = requests.post(args.url, json=payload, timeout=10)
            if not r.ok:
                raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
            preds.append(float(r.json()["predicted_price"]))
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"error: {e}")
        latencies.append((time.perf_counter() - start) * 1000)

    lat = sorted(latencies)
    print("\n===== Monitoring summary =====")
    print(f"requests      : {args.n}")
    print(f"errors        : {errors} ({errors / args.n:.1%})")
    print(f"latency mean  : {statistics.mean(lat):.1f} ms")
    print(f"latency p95   : {lat[max(int(0.95 * len(lat)) - 1, 0)]:.1f} ms")
    if preds:
        print(f"prediction    : min={min(preds):,.0f}  "
              f"mean={statistics.mean(preds):,.0f}  max={max(preds):,.0f} THB")


if __name__ == "__main__":
    main()
