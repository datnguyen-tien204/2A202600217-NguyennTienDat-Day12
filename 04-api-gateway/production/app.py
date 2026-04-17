"""
PRODUCTION — Full Security Stack

OPTIMIZATIONS:
  - Dùng ask_async() thay vì ask() để không block event loop
  - Thêm request_id để trace requests qua logs
  - Structured logging nhất quán
  - Thêm /admin/rate-stats endpoint để monitor rate limiter

Kết hợp:
  ✅ JWT Authentication
  ✅ Role-based access (user / admin)
  ✅ Rate limiting (sliding window, thread-safe)
  ✅ Cost guard (daily budget, bug-fixed)
  ✅ Input validation (Pydantic)
  ✅ Security headers
  ✅ Request tracing (request_id)
"""
import os
import time
import uuid
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from auth import verify_token, authenticate_user, create_token
from rate_limiter import rate_limiter_user, rate_limiter_admin
from cost_guard import cost_guard
from utils.mock_llm import ask_async

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "env": ENVIRONMENT}))
    yield
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title="Agent — Full Security Stack",
    version="3.0.0",
    lifespan=lifespan,
    # ✅ Ẩn /docs trong production
    docs_url="/docs" if ENVIRONMENT != "production" else None,
    redoc_url=None,
)

# ──────────────────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """
    Thêm:
      - Security headers vào mọi response
      - Request ID để trace qua logs
      - Structured access log
    """
    # OPTIMIZATION: Thêm request_id để dễ trace khi debug
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    start = time.time()
    response: Response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 1)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request_id
    response.headers.pop("server", None)

    logger.info(json.dumps({
        "event": "http",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": duration_ms,
    }))

    return response


# ──────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000,
                          description="Câu hỏi gửi đến AI agent")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


# ──────────────────────────────────────────────────────────
# Auth Endpoints
# ──────────────────────────────────────────────────────────

@app.post("/auth/token", tags=["Auth"])
def login(body: LoginRequest):
    """Public endpoint. Đổi username/password lấy JWT token."""
    user = authenticate_user(body.username, body.password)
    token = create_token(user["username"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": 60,
    }


# ──────────────────────────────────────────────────────────
# Protected Agent Endpoint
# ──────────────────────────────────────────────────────────

@app.post("/ask", tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    user: dict = Depends(verify_token),
):
    username = user["username"]
    role = user["role"]

    # Rate limiting — theo role
    limiter = rate_limiter_admin if role == "admin" else rate_limiter_user
    rate_info = limiter.check(username)

    # Cost check trước khi gọi LLM
    cost_guard.check_budget(username)

    # ✅ OPTIMIZATION: Dùng ask_async để không block event loop
    response_text = await ask_async(body.question)

    # Ghi nhận usage (mock token count)
    input_tokens = len(body.question.split()) * 2
    output_tokens = len(response_text.split()) * 2
    usage = cost_guard.record_usage(username, input_tokens, output_tokens)

    return {
        "question": body.question,
        "answer": response_text,
        "request_id": getattr(request.state, "request_id", None),
        "usage": {
            "requests_remaining": rate_info["remaining"],
            "budget_remaining_usd": round(
                cost_guard.daily_budget_usd - usage.total_cost_usd, 4
            ),
        },
    }


@app.get("/me/usage", tags=["User"])
def my_usage(user: dict = Depends(verify_token)):
    """Xem usage của bản thân."""
    return cost_guard.get_usage(user["username"])


@app.get("/admin/stats", tags=["Admin"])
def admin_stats(user: dict = Depends(verify_token)):
    """Admin only: xem tổng stats."""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return {
        "global_cost_usd": cost_guard.global_cost,
        "global_budget_usd": cost_guard.global_daily_budget_usd,
        "global_budget_used_pct": round(
            cost_guard.global_cost / cost_guard.global_daily_budget_usd * 100, 1
        ),
    }


@app.get("/admin/rate-stats", tags=["Admin"])
def rate_stats(user: dict = Depends(verify_token)):
    """Admin only: xem rate limiter stats."""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return {
        "active_users_user_tier": rate_limiter_user.active_users_count(),
        "active_users_admin_tier": rate_limiter_admin.active_users_count(),
    }


# ──────────────────────────────────────────────────────────
# Health Checks (public)
# ──────────────────────────────────────────────────────────

@app.get("/health", tags=["Ops"])
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "security": "JWT + RateLimit + CostGuard",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("\n=== Demo credentials ===")
    print("  student / demo123  (10 req/min, $1/day budget)")
    print("  teacher / teach456 (100 req/min, $1/day budget)")
    print(f"\nDocs: http://localhost:{port}/docs\n")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
