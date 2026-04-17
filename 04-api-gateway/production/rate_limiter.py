"""
In-Memory Rate Limiter — Sliding Window Counter

OPTIMIZATIONS:
  - Thêm cleanup() để giải phóng memory cho inactive users
    → Tránh memory leak khi có nhiều unique users
  - Thread-safe với threading.Lock
  - Thêm get_stats() để monitor
  - Thêm cleanup threshold để tự động dọn dẹp

Algorithm: Sliding Window Counter
- Mỗi user có 1 bucket (deque of timestamps)
- Bucket đếm request trong window (60 giây)
- Vượt quá limit → trả về 429 Too Many Requests

Trong production: thay bằng Redis-based rate limiter để scale ngang.
"""
import time
import threading
from collections import defaultdict, deque
from typing import Optional

from fastapi import HTTPException


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        cleanup_interval_seconds: int = 300,  # Cleanup mỗi 5 phút
    ):
        """
        Args:
            max_requests: Số request tối đa trong window
            window_seconds: Khoảng thời gian (giây)
            cleanup_interval_seconds: Bao lâu cleanup một lần
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds

        # key: user_id → deque của timestamps
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()  # ✅ Thread-safe
        self._last_cleanup = time.time()

    def _cleanup_stale(self, now: float) -> None:
        """
        OPTIMIZATION: Xóa buckets của users không hoạt động.
        Tránh memory leak khi số lượng unique users lớn.
        """
        if now - self._last_cleanup < self.cleanup_interval_seconds:
            return

        cutoff = now - self.window_seconds
        stale_users = [
            uid for uid, window in self._windows.items()
            if not window or window[-1] < cutoff
        ]
        for uid in stale_users:
            del self._windows[uid]

        self._last_cleanup = now

    def check(self, user_id: str) -> dict:
        """
        Kiểm tra user có vượt rate limit không.
        Raise 429 nếu vượt quá.
        Returns: dict với thông tin còn lại.
        """
        now = time.time()

        with self._lock:  # ✅ Thread-safe
            # Cleanup stale entries theo chu kỳ
            self._cleanup_stale(now)

            window = self._windows[user_id]

            # Loại bỏ timestamps cũ (ngoài window)
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self.max_requests:
                oldest = window[0]
                retry_after = int(oldest + self.window_seconds - now) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": self.max_requests,
                        "window_seconds": self.window_seconds,
                        "retry_after_seconds": retry_after,
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(oldest + self.window_seconds)),
                        "Retry-After": str(retry_after),
                    },
                )

            # Record request
            window.append(now)
            remaining = self.max_requests - len(window)

            return {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset_at": int(now + self.window_seconds),
            }

    def get_stats(self, user_id: str) -> dict:
        """Trả về stats của user (không check limit)."""
        now = time.time()
        with self._lock:
            window = self._windows.get(user_id, deque())
            cutoff = now - self.window_seconds
            active = sum(1 for t in window if t >= cutoff)
        return {
            "requests_in_window": active,
            "limit": self.max_requests,
            "window_seconds": self.window_seconds,
            "remaining": max(0, self.max_requests - active),
        }

    def active_users_count(self) -> int:
        """Số users đang có request trong window (cho monitoring)."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            return sum(
                1 for w in self._windows.values()
                if w and w[-1] >= cutoff
            )


# Singleton instances cho các tiers khác nhau
rate_limiter_user = RateLimiter(
    max_requests=10,
    window_seconds=60,
    cleanup_interval_seconds=300,
)   # User: 10 req/phút

rate_limiter_admin = RateLimiter(
    max_requests=100,
    window_seconds=60,
    cleanup_interval_seconds=600,
)  # Admin: 100 req/phút
