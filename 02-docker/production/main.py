"""
Agent production-ready — dùng trong Docker production stack.

OPTIMIZATIONS:
  - asyncio.sleep thay vì time.sleep trong lifespan
  - Pydantic BaseModel cho request validation  
  - timezone-aware datetime (UTC)
  - Proper type hints
"""
import os
import time
import logging
import json
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from utils.mock_llm import ask_async

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({"event": "startup", "env": ENVIRONMENT}))
    await asyncio.sleep(0.1)  # ✅ non-blocking init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title="Agent (Docker Production)",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/")
def root():
    return {
        "app": "AI Agent",
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
    }


@app.post("/ask")
async def ask_agent(body: AskRequest, request: Request):
    logger.info(json.dumps({
        "event": "request",
        "q_len": len(body.question),
        "client": request.client.host if request.client else "unknown",
    }))
    answer = await ask_async(body.question)
    return {"question": body.question, "answer": answer, "version": APP_VERSION}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ timezone-aware
    }


@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(503, "Service not ready")
    return {"ready": True}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=30)
