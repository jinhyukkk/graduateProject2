"""
SC-TSQL Dashboard Backend -- FastAPI entry point.

Run with:
    cd backend
    uvicorn main:app --reload --port 8000

Or from project root:
    uvicorn backend.main:app --reload --port 8000
"""

import sys
import os

# Ensure project root is on sys.path for src/ imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# .env 파일 자동 로드 (프로젝트 루트의 .env)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass  # python-dotenv 없으면 환경변수를 직접 설정해야 함

# Also ensure the backend package itself is importable when running from backend/
BACKEND_PARENT = os.path.dirname(os.path.abspath(__file__))
BACKEND_PARENT_DIR = os.path.dirname(BACKEND_PARENT)
if BACKEND_PARENT_DIR not in sys.path:
    sys.path.insert(0, BACKEND_PARENT_DIR)

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import query, experiment, config

app = FastAPI(
    title="SC-TSQL Dashboard API",
    description="Backend API for the SC-TSQL Text-to-SQL experiment dashboard.",
    version="1.0.0",
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:5174",   # Vite fallback port
        "http://127.0.0.1:5174",
        "http://localhost:3000",   # Docker nginx
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Health check (Docker healthcheck용) ──
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

# ── Routers ──
app.include_router(config.router)
app.include_router(query.router)
app.include_router(experiment.router)
