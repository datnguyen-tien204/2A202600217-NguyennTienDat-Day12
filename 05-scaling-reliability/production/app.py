"""
PRODUCTION — Stateless Agent với Redis Session

OPTIMIZATIONS:
  - Dùng async Redis (redis.asyncio) để không block event loop
    → Khi dùng redis.Redis() bình thường, mỗi Redis call block thread
    → Với async Redis, nhiều requests chạy đồng thời mà không block nhau
  - Connection pool cho Redis
  - Tách session logic vào SessionStore class
  - Thêm proper TTL reset khi append history

Stateless = agent không giữ state trong memory.
Mọi state (session, conversation history) lưu trong Redis.

Tại sao stateless quan trọng khi scale?
  Instance 1: User A gửi request 1 → lưu session trong memory
  Instance 2: User A gửi request 2 → KHÔNG có session! Bug!

  ✅ Giải pháp: Lưu session trong Redis
  Bất kỳ instance nào cũng đọc được session của user.
"""
import os
import time
import json
import logging
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from utils.mock_llm import ask_async

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID", f"instance-{uuid.uuid4().hex[:6]}")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 jam default
MAX_HISTORY = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))   # 10 turns


# ──────────────────────────────────────────────────────────
# Session Store — Redis-backed với async client
# ──────────────────────────────────────────────────────────

class SessionStore:
    """
    Redis-backed session storage.
    OPTIMIZATION: Dùng redis.asyncio (non-blocking) thay vì redis.Redis (blocking).
    Khi không có Redis → fallback ke in-memory dict (TIDAK bisa digunakan untuk scaling).
    """

    def __init__(self):
        self._redis = None
        self._memory: dict = {}
        self.use_redis = False
        self.require_redis = os.getenv("REQUIRE_REDIS", "false").lower() == "true" or os.getenv("ENVIRONMENT", "development").lower() == "production"

    async def connect(self) -> None:
        """Kết nối Redis khi app startup."""
        try:
            import redis.asyncio as aioredis  # ✅ Async Redis client
            self._redis = await aioredis.from_url(
                REDIS_URL,
                decode_responses=True,
                max_connections=20,  # Connection pool
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            await self._redis.ping()
            self.use_redis = True
            logger.info(f"✅ Connected to Redis: {REDIS_URL}")
        except Exception as e:
            if self.require_redis:
                logger.exception("Redis is required but unavailable")
                raise RuntimeError(f"Redis is required but unavailable: {e}") from e
            self.use_redis = False
            logger.warning(f"⚠️ Redis not available ({e}) — using in-memory (not scalable!)")

    async def disconnect(self) -> None:
        """Đóng Redis connection gracefully."""
        if self._redis:
            await self._redis.aclose()

    async def get(self, session_id: str) -> dict:
        key = f"session:{session_id}"
        if self.use_redis:
            data = await self._redis.get(key)
            return json.loads(data) if data else {}
        return self._memory.get(key, {})

    async def set(self, session_id: str, data: dict) -> None:
        key = f"session:{session_id}"
        serialized = json.dumps(data)
        if self.use_redis:
            await self._redis.setex(key, SESSION_TTL, serialized)
        else:
            self._memory[key] = data

    async def delete(self, session_id: str) -> bool:
        key = f"session:{session_id}"
        if self.use_redis:
            deleted = await self._redis.delete(key)
            return bool(deleted)
        return bool(self._memory.pop(key, None))

    async def is_healthy(self) -> bool:
        if not self.use_redis:
            return True  # in-memory luôn "healthy"
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


session_store = SessionStore()


# ──────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await session_store.connect()
    logger.info(f"Instance {INSTANCE_ID} ready | storage={'redis' if session_store.use_redis else 'in-memory'}")
    yield
    await session_store.disconnect()
    logger.info(f"Instance {INSTANCE_ID} shutdown")


app = FastAPI(
    title="Stateless Agent",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="None = tạo session mới")


# ──────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────

async def append_to_history(session_id: str, role: str, content: str) -> list:
    """Thêm message vào conversation history, reset TTL."""
    session = await session_store.get(session_id)
    history = session.get("history", [])
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Giữ tối đa MAX_HISTORY messages (10 turns)
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    session["history"] = history
    await session_store.set(session_id, session)  # ✅ TTL reset với mỗi activity
    return history


# ──────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(body: ChatRequest):
    """
    Multi-turn conversation với session management.
    Gửi session_id trong các request tiếp theo để tiếp tục cuộc trò chuyện.
    Agent có thể chạy trên bất kỳ instance nào — state trong Redis.
    """
    session_id = body.session_id or str(uuid.uuid4())

    await append_to_history(session_id, "user", body.question)

    # ✅ Dùng ask_async để không block event loop
    answer = await ask_async(body.question)

    history = await append_to_history(session_id, "assistant", answer)
    turn = sum(1 for m in history if m["role"] == "user")

    return {
        "session_id": session_id,
        "question": body.question,
        "answer": answer,
        "turn": turn,
        "served_by": INSTANCE_ID,  # ← thấy rõ bất kỳ instance nào cũng serve được
        "storage": "redis" if session_store.use_redis else "in-memory",
    }


@app.get("/chat/{session_id}/history")
async def get_history(session_id: str):
    """Xem conversation history của một session."""
    session = await session_store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id!r} not found or expired")
    messages = session.get("history", [])
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }


@app.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    """Xóa session (user logout)."""
    deleted = await session_store.delete(session_id)
    if not deleted:
        raise HTTPException(404, f"Session {session_id!r} not found")
    return {"deleted": session_id}


# ──────────────────────────────────────────────────────────
# Health / Metrics
# ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    redis_ok = await session_store.is_healthy()
    status = "ok" if redis_ok else "degraded"
    return {
        "status": status,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "storage": "redis" if session_store.use_redis else "in-memory",
        "redis_healthy": redis_ok,
    }


@app.get("/ready")
async def ready():
    if not await session_store.is_healthy():
        raise HTTPException(503, "Redis not available")
    return {"ready": True, "instance": INSTANCE_ID}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=30)
