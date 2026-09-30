import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    # ถ้ายังไม่มีโมเดล ให้เทรนแบบเล็กๆ อัตโนมัติ
    if not (ROOT / "model" / "model.joblib").exists():
        from src import train
        train.main(n_samples=600)