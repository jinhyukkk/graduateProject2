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

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import query, experiment, config
from backend.services.tsql_service import warmup_default_pipeline


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """부팅 직후 SC-TSQL 파이프라인을 백그라운드에서 워밍업한다.

    SchemaLinker FAISS 인덱스 빌드 + NLI 모델 로드를 첫 사용자 쿼리 이전에
    완료해 콜드 스타트를 제거한다. uvicorn은 워밍업을 기다리지 않고 즉시
    요청을 받기 시작한다.
    """
    loop = asyncio.get_running_loop()
    warmup_task = loop.run_in_executor(None, warmup_default_pipeline)
    try:
        yield
    finally:
        # 워밍업이 진행 중이라면 정리되도록 잠시 기다린다 (실패해도 종료에 영향 없음)
        if not warmup_task.done():
            warmup_task.cancel()


app = FastAPI(
    title="SC-TSQL Dashboard API",
    description="Backend API for the SC-TSQL Text-to-SQL experiment dashboard.",
    version="1.0.0",
    lifespan=lifespan,
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
