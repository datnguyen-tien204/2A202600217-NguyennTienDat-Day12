from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.vinmec_agent import chat as agent_chat
from app.core.auth import require_client_key, require_trainer_key, resolve_request_scopes
from app.core.config import settings
from app.core.cost_guard import GLOBAL_COST_SCOPE, check_and_record_cost, get_monthly_cost
from app.core.rate_limiter import enforce_rate_limit, ensure_session_owner

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
        logger.info(json.dumps({"event": "sentry_init", "ok": True}))
    except ImportError:
        logger.warning(json.dumps({"event": "sentry_skip", "reason": "sentry-sdk not installed"}))

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0
_redis: Optional[aioredis.Redis] = None


def _safe_redis_target() -> str:
    target = settings.redis_url.rsplit("@", 1)[-1]
    return target.removeprefix("redis://").removeprefix("rediss://")


async def _get_redis() -> aioredis.Redis:
    if not _redis:
        raise HTTPException(503, "Redis chưa sẵn sàng.")
    return _redis


async def _get_history(redis: aioredis.Redis, session_id: str) -> list[dict]:
    try:
        raw = await redis.get(f"session:{session_id}")
        return json.loads(raw) if raw else []
    except Exception:
        return []


async def _save_history(redis: aioredis.Redis, session_id: str, history: list[dict]):
    try:
        await redis.setex(
            f"session:{session_id}",
            settings.redis_session_ttl,
            json.dumps(history[-40:], ensure_ascii=False),
        )
    except Exception as exc:
        logger.warning(json.dumps({"event": "session_save_fail", "error": str(exc)}))


async def _run_agent_chat(message: str, history: list[dict]) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, agent_chat, message, history)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis, _is_ready

    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
            }
        )
    )

    _redis = aioredis.from_url(settings.redis_url, decode_responses=True, max_connections=50)
    try:
        await _redis.ping()
        logger.info(json.dumps({"event": "redis_ok", "target": _safe_redis_target()}))
    except Exception as exc:
        logger.error(json.dumps({"event": "redis_fail", "error": str(exc)}))
        raise

    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    if _redis:
        await _redis.aclose()
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="VinmecPrep AI - single-service production API",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Trainer-Key", "X-User-ID"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    global _request_count, _error_count

    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.time()
    _request_count += 1

    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        raise

    duration_ms = round((time.time() - start) * 1000, 1)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = request_id
    if "server" in response.headers:
        del response.headers["server"]

    logger.info(
        json.dumps(
            {
                "event": "http",
                "rid": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": duration_ms,
                "ip": request.client.host if request.client else "",
            }
        )
    )
    return response


class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    history: list[Message] = Field(default_factory=list, max_length=40)


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    blocked: bool
    guard_result: str
    request_id: str
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "deploy_mode": "single-service",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-Trainer-Key)",
            "auth": "X-API-Key bat buoc cho /chat",
        },
    }


@app.get("/health", tags=["Operations"])
async def health():
    redis = _redis
    try:
        if redis:
            await redis.ping()
        redis_ok = bool(redis)
    except Exception:
        redis_ok = False

    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "redis": "ok" if redis_ok else "error",
            "llm": settings.llm_model,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
async def ready():
    redis = await _get_redis()
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    try:
        await redis.ping()
    except Exception as exc:
        logger.warning(json.dumps({"event": "ready_check_fail", "error": str(exc)}))
        raise HTTPException(503, "Redis chưa sẵn sàng")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
async def metrics(_key: str = Depends(require_trainer_key)):
    redis = await _get_redis()
    monthly_cost = await get_monthly_cost(redis, GLOBAL_COST_SCOPE)
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "monthly_cost_usd": round(monthly_cost, 6),
        "monthly_budget_usd": settings.monthly_budget_usd,
        "budget_used_pct": round(monthly_cost / max(settings.monthly_budget_usd, 0.0001) * 100, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(
    req: ChatRequest,
    request: Request,
    client_key: str = Depends(require_client_key),
):
    redis = await _get_redis()
    session_id = req.session_id or str(uuid.uuid4())
    rid = getattr(request.state, "request_id", "")
    scopes = resolve_request_scopes(request, client_key, session_id)
    client_scope = scopes["client_scope"]
    session_scope = scopes.get("session_scope")

    history = [m.model_dump() for m in req.history] if req.history else await _get_history(redis, session_id)

    await ensure_session_owner(redis, session_id, client_scope)
    await enforce_rate_limit(redis, client_scope, session_scope)
    input_tokens_est = len(req.message.split()) * 2 + len(history) * 10
    await check_and_record_cost(redis, client_scope, input_tokens_est, 0)

    logger.info(
        json.dumps(
            {
                "event": "chat_submit",
                "rid": rid,
                "session_id": session_id,
                "msg_len": len(req.message),
            }
        )
    )

    result = await _run_agent_chat(req.message, history)
    blocked = bool(result.get("blocked", False))
    reply = result.get("reply", "Đã xảy ra lỗi. Vui lòng thử lại hoặc gọi 1900 54 61 54.")

    if not blocked:
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": reply})
        await _save_history(redis, session_id, history)

    output_tokens_est = len(reply.split()) * 2
    await check_and_record_cost(redis, client_scope, 0, output_tokens_est)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        blocked=blocked,
        guard_result=result.get("guard_result", ""),
        request_id=rid,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/", response_model=ChatResponse, tags=["Chat"], include_in_schema=False)
async def chat_root(
    req: ChatRequest,
    request: Request,
    client_key: str = Depends(require_client_key),
):
    return await chat_endpoint(req, request, client_key)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    global _error_count
    _error_count += 1
    logger.error(json.dumps({"event": "unhandled_error", "path": request.url.path, "error": str(exc)}), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Đã xảy ra lỗi. Vui lòng thử lại hoặc gọi 1900 54 61 54."},
    )


def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    import uvicorn

    logger.info(
        json.dumps(
            {
                "event": "main_start",
                "host": settings.host,
                "port": settings.port,
                "workers": settings.api_workers,
            }
        )
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.api_workers,
        reload=settings.debug,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=30,
    )
