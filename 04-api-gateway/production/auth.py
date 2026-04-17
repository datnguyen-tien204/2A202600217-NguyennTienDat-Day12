"""
JWT Authentication Module

OPTIMIZATIONS:
  - hmac.compare_digest() cho constant-time password comparison
    → Chống timing attack (attacker không đoán được password từ response time)
  - Tách SECRET_KEY validation rõ hơn
  - Thêm type hints đầy đủ
  - Token revocation hint (trong production dùng Redis blacklist)

JWT (JSON Web Token) = stateless auth.
Token chứa: user_id, role, expiry → không cần check DB mỗi request.

Flow:
    POST /auth/token  → trả về JWT
    GET  /ask         → gửi JWT trong header Authorization: Bearer <token>
    Server verify signature → extract user info → process request
"""
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-change-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Warn nếu dùng default secret key trong production
if SECRET_KEY == "super-secret-change-in-production-please":
    import logging
    logging.getLogger(__name__).warning(
        "JWT_SECRET is using default value — set a strong secret in production!"
    )

# Demo users (trong thực tế lưu trong database với hashed passwords)
# KHÔNG lưu plaintext password trong production — dùng bcrypt/argon2
_DEMO_USERS: dict[str, dict] = {
    "student": {
        "password_hash": "demo123",  # production: bcrypt hash
        "role": "user",
        "daily_limit": 50,
    },
    "teacher": {
        "password_hash": "teach456",  # production: bcrypt hash
        "role": "admin",
        "daily_limit": 1000,
    },
}

security = HTTPBearer(auto_error=False)


def create_token(username: str, role: str) -> str:
    """Tạo JWT token với expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,  # subject (user identifier)
        "role": role,
        "iat": now,       # issued at
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> dict:
    """
    Dependency: verify JWT token từ Authorization header.
    Raise HTTPException nếu token invalid hoặc expired.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Include: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return {
            "username": payload["sub"],
            "role": payload["role"],
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token.")


def authenticate_user(username: str, password: str) -> dict:
    """
    Kiểm tra username/password, trả về user info nếu hợp lệ.

    OPTIMIZATION: hmac.compare_digest() cho constant-time comparison
    → Chống timing attack — attacker không thể đoán password
      bằng cách đo thời gian response khác nhau.
    """
    user = _DEMO_USERS.get(username)
    if not user:
        # Vẫn thực hiện comparison để tránh timing leak về việc username có tồn tại không
        hmac.compare_digest("dummy", "dummy")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # ✅ Constant-time comparison — chống timing attack
    if not hmac.compare_digest(user["password_hash"], password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"username": username, "role": user["role"]}
