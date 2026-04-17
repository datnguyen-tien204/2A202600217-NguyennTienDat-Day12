"""
✅ PRODUCTION-READY — 12-Factor Compliant Agent

So sánh với develop/app.py để thấy sự khác biệt:
  ✅ Config từ environment variables
  ✅ Structured JSON logging
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown (SIGTERM)
  ✅ 0.0.0.0 binding (chạy được trong container)
  ✅ Port từ PORT env var (Railway/Render inject tự động)
  ✅ asyncio.sleep thay vì time.sleep trong lifespan (không block event loop)
  ✅ Pydantic BaseModel cho request validation
"""
import os
import signal
import logging
import json
import time
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from config import settings
from utils.mock_llm import ask_async

# ✅ Structured JSON logging — dễ parse trong log aggregator (Datadog, Loki...)
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False  # readiness flag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ✅ Lifecycle management:
    - startup: khởi tạo connections, load model
    - shutdown: đóng connections gracefully

    OPTIMIZATION: Dùng asyncio.sleep thay vì time.sleep
    → Không block event loop trong khi khởi động.
    """
    global _is_ready

    # --- Startup ---
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.environment,
        "port": settings.port,
    }))
    await asyncio.sleep(0.1)  # ✅ Non-blocking init simulation
    _is_ready = True
    logger.info("Agent is ready to serve requests")

    yield  # App running

    # --- Shutdown ---
    _is_ready = False
    logger.info("Agent shutting down gracefully — finishing in-flight requests...")
    await asyncio.sleep(0.1)  # ✅ Cho request hiện tại hoàn thành
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    # ✅ Ẩn docs trong production
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# ✅ CORS — chỉ cho phép origins được cấu hình
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ============================================================
# Request Models — Pydantic validation
# ============================================================

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Câu hỏi gửi đến AI agent")


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }


@app.post("/ask")
async def ask_agent(body: AskRequest, request: Request):
    # ✅ Structured logging — KHÔNG log secrets
    logger.info(json.dumps({
        "event": "agent_request",
        "question_length": len(body.question),
        "client_ip": request.client.host if request.client else "unknown",
    }))

    # ✅ Dùng async version để không block event loop
    response = await ask_async(body.question)

    logger.info(json.dumps({
        "event": "agent_response",
        "response_length": len(response),
    }))

    return {
        "question": body.question,
        "answer": response,
        "model": settings.llm_model,
    }


# ============================================================
# HEALTH CHECK — Required for cloud deployment
# ============================================================

@app.get("/health")
def health_check():
    """
    ✅ Liveness probe: "Agent có còn sống không?"
    Platform gọi endpoint này định kỳ.
    Nếu trả về non-200 → platform restart container.
    """
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def readiness_check():
    """
    ✅ Readiness probe: "Agent có sẵn sàng nhận request chưa?"
    Load balancer dùng cái này để quyết định có route traffic vào không.
    Trả về 503 khi đang khởi động hoặc quá tải.
    """
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Agent not ready yet")
    return {"ready": True}


@app.get("/metrics")
def metrics():
    """✅ Basic metrics endpoint — có thể scrape bởi Prometheus."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "environment": settings.environment,
        "version": settings.app_version,
    }


# ============================================================
# GRACEFUL SHUTDOWN
# ============================================================

def handle_sigterm(*args):
    """
    ✅ Xử lý SIGTERM — signal mà platform gửi khi muốn tắt container.
    Cho phép request hiện tại hoàn thành trước khi tắt.
    """
    logger.info("Received SIGTERM — initiating graceful shutdown")


signal.signal(signal.SIGTERM, handle_sigterm)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run(
        "app:app",
        host=settings.host,    # ✅ 0.0.0.0 — nhận kết nối từ bên ngoài container
        port=settings.port,    # ✅ từ PORT env var
        reload=settings.debug, # ✅ reload chỉ khi DEBUG=true
        timeout_graceful_shutdown=30,
    )
