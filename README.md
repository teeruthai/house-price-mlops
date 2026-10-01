# House Price MLOps

ระบบทำนายราคาบ้านแบบครบวงจร MLOps: ฝึกโมเดลและบันทึกผลด้วย MLflow → ลงทะเบียนโมเดล → เสิร์ฟผ่าน FastAPI ใน Docker → CI/CD ด้วย GitHub Actions → จำลองการ monitoring

> โปรเจกต์นี้ใช้ข้อมูลจำลอง (synthetic data) ที่สร้างในโค้ด ราคาที่ทำนายจึงไม่ใช่ราคาตลาดจริง

## สถาปัตยกรรม

```
src/train.py ──► MLflow (tracking + registry) ──► model/model.joblib
                                                        │
                                                        ▼
tests/ (pytest) ◄── GitHub Actions ──► Docker image ◄── src/app.py (FastAPI)
                                                        │
                                          scripts/simulate_traffic.py (monitoring)
```

## โครงสร้างโปรเจกต์

```
.github/workflows/ci-cd.yml   # CI/CD: train -> test -> build -> deploy (จำลอง)
src/train.py                  # เทรน 2 โมเดล, log MLflow, register, export โมเดล
src/app.py                    # FastAPI: /health, /predict, /metrics
tests/                        # pytest สำหรับ API
scripts/simulate_traffic.py   # ยิง request จำลองเพื่อวัด latency/error
Dockerfile                    # build image ของ API
requirements.txt              # dependencies สำหรับเทรน + ทดสอบ
requirements-api.txt          # dependencies สำหรับ API (ใช้ใน Docker)
```

## เริ่มต้นใช้งาน

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
```

### 1) เทรนโมเดลและบันทึกลง MLflow

```bash
python src/train.py
```

สคริปต์จะ:

- สร้างข้อมูลจำลอง 3,000 แถว แล้วแบ่ง train/test 80/20
- เทรน 2 อัลกอริทึม คือ **Linear Regression** และ **Random Forest** (200 ต้นไม้, max_depth 12)
- บันทึก params และ metrics (RMSE, MAE, R²) ของทั้งสองโมเดลลง MLflow
- เลือกโมเดลที่ **RMSE ต่ำสุด** ลงทะเบียนเป็น `house-price-model` (version 1) และตั้ง alias `production`
- export โมเดลไว้ที่ `model/` (`model.joblib`, `metadata.json`, `baseline_stats.json`)

ดูผลใน MLflow UI (ข้อมูลเก็บใน `mlflow.db` จึงต้องระบุ backend ให้ตรง):

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

จากนั้นเปิด <http://127.0.0.1:5000> หน้า **Experiments** ใช้เปรียบเทียบ run และหน้า **Models** ดูโมเดลที่ลงทะเบียน

**ผลการเปรียบเทียบโมเดล** (ใส่ตัวเลขจากการรันของคุณ)

| Model | RMSE (THB) | MAE (THB) | R² |
|-------|-----------:|----------:|---:|
| Linear Regression | 1,051,824 | 762,652 | 0.9229 |
| Random Forest | **504,091** | **362,996** | **0.9823** |

โมเดลที่ถูกเลือก: **Random Forest** (RMSE ต่ำกว่า Linear Regression ประมาณ 52%) ซึ่งสมเหตุสมผล เพราะข้อมูลจำลองมีความสัมพันธ์ที่ไม่เป็นเส้นตรง เช่น ราคาต่อ ตร.ม. ต่างกันตามทำเล และมีผลของอายุบ้าน

โมเดลถูกลงทะเบียนเป็น `house-price-model` และตั้ง alias `production` (เลขเวอร์ชันเพิ่มขึ้นทุกครั้งที่รัน `train.py` ในฐานข้อมูล MLflow เดิม เช่น รันครั้งที่สองจะได้ v2 ส่วนบน CI ที่เริ่มจากฐานข้อมูลว่างจะได้ v1)

### 2) รัน API

```bash
uvicorn src.app:app --port 8000
```

เอกสาร API แบบโต้ตอบอยู่ที่ <http://127.0.0.1:8000/docs>

| Endpoint | Method | คำอธิบาย |
|----------|--------|----------|
| `/health` | GET | สถานะระบบและเวอร์ชันโมเดล |
| `/predict` | POST | ทำนายราคาบ้าน |
| `/metrics` | GET | จำนวน request และ latency เฉลี่ย |

**Input ของ `/predict`**

| Field | ชนิด | เงื่อนไข |
|-------|------|----------|
| `area_sqm` | float | มากกว่า 10 และน้อยกว่า 2000 |
| `bedrooms` | int | 1–10 |
| `bathrooms` | int | 1–10 (ค่าเริ่มต้น 1) |
| `age_years` | int | 0–100 (ค่าเริ่มต้น 0) |
| `location` | string | `city_center`, `suburb` หรือ `rural` |

**ตัวอย่าง request (PowerShell)**

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/predict -ContentType "application/json" -Body '{"area_sqm":120,"bedrooms":3,"bathrooms":2,"age_years":5,"location":"suburb"}'
```

**ตัวอย่าง request (curl บน macOS/Linux)**

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"area_sqm":120,"bedrooms":3,"bathrooms":2,"age_years":5,"location":"suburb"}'
```

**ตัวอย่าง response**

```json
{
  "predicted_price": 6223000.0,
  "currency": "THB",
  "model_name": "house-price-model",
  "model_version": "1"
}
```

ถ้าส่งค่าที่ไม่ตรงเงื่อนไข (เช่น `location` ที่ไม่รองรับ) API จะตอบ `422 Unprocessable Entity` พร้อมบอกว่า field ไหนผิด ทุก request ที่ทำนายสำเร็จจะถูกบันทึกลง `logs/predictions.jsonl` เพื่อใช้ monitoring

### 3) รันด้วย Docker

ต้องเทรนโมเดลก่อน เพื่อให้มีโฟลเดอร์ `model/`

```bash
python src/train.py
docker build -t house-price-api .
docker run -p 8000:8000 house-price-api
```

## ทดสอบ

```bash
pytest -v
```

## CI/CD (GitHub Actions)

ไฟล์ `.github/workflows/ci-cd.yml` ทำงานทุกครั้งที่ push ประกอบด้วย 3 job

1. **test**: ติดตั้ง dependencies → เทรนโมเดลและ register ใน MLflow → รัน `pytest` → อัปโหลดโฟลเดอร์ `model/` เป็น artifact
2. **build**: ดาวน์โหลดโมเดล → build Docker image → smoke test (เรียก `/health` และ `/predict` จาก container จริง) → บันทึก image เป็น artifact
3. **deploy** (เฉพาะ branch `main`): **จำลอง**การ deploy ไปยัง environment `staging` โดยพิมพ์ขั้นตอนที่จะเกิดขึ้นบนคลาวด์ (Azure Container Apps / AWS ECS / GCP Cloud Run) ไม่ได้เชื่อมต่อบัญชีคลาวด์จริง

## Monitoring

`scripts/simulate_traffic.py` สุ่มข้อมูลบ้านส่งเข้า `/predict` แล้วสรุป error, latency และช่วงราคาที่ทำนาย

```bash
pip install requests
python scripts/simulate_traffic.py --n 200
```

ผลจากการรันจริง (200 requests บนเครื่อง local)

| ตัวชี้วัด | ค่า |
|-----------|-----|
| Errors | 0 (0.0%) |
| Latency เฉลี่ย | 77.7 ms |
| Latency p95 | 148.3 ms |
| ราคาที่ทำนาย (ต่ำสุด / เฉลี่ย / สูงสุด) | 1,317,000 / 9,834,220 / 25,788,000 THB |

## แนวทางต่อยอด

- ใช้ `model/baseline_stats.json` (ค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐานของข้อมูลเทรน) เปรียบเทียบกับข้อมูลใน `logs/predictions.jsonl` เพื่อตรวจ data drift
- เพิ่มเงื่อนไขใน CI ให้ล้มเหลวเมื่อ RMSE แย่กว่าเกณฑ์ที่กำหนด
- deploy ขึ้นคลาวด์จริงและเพิ่ม environment `production` ที่ต้องอนุมัติก่อน deploy
