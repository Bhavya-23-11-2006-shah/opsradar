"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _path(env_name: str, default: Path) -> Path:
    raw = os.getenv(env_name)
    return Path(raw).resolve() if raw else default


DATA_DIR = _path("OPSRADAR_DATA_DIR", BASE_DIR / "data")
DEMO_DIR = _path("OPSRADAR_DEMO_DIR", BASE_DIR / "demo_data")
CACHE_DIR = DATA_DIR / "cache"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'opsradar.db').as_posix()}")

LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "none").strip().lower()
LLM_API_KEY = (os.getenv("LLM_API_KEY") or "").strip()
LLM_MODEL = (os.getenv("LLM_MODEL") or "").strip()

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

try:
    MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024)
except ValueError:
    MAX_UPLOAD_BYTES = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

ACTOR = "Ops manager"
