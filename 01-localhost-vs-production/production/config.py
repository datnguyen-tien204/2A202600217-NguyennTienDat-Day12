"""
✅ PRODUCTION — Centralized Config Management (12-Factor: Config in Env)

Tất cả config đọc từ environment variables.
- Không có giá trị nhạy cảm trong code
- Dễ thay đổi giữa dev/staging/production
- Validation rõ ràng — fail fast nếu thiếu config quan trọng

OPTIMIZATION: Dùng __post_init__ để validate sau khi khởi tạo,
đảm bảo Settings object luôn hợp lệ trước khi dùng.
"""
import os
import logging
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # LLM (optional — chỉ warn nếu thiếu, không crash)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "500")))

    # Security
    api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    allowed_origins: list = field(
        default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "*").split(",")
    )

    def __post_init__(self):
        """Validate config ngay sau khi khởi tạo."""
        self.validate()

    def validate(self) -> "Settings":
        """Fail fast nếu thiếu config bắt buộc trong production."""
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set — using mock LLM")

        if self.environment == "production":
            if not self.api_key:
                raise ValueError("AGENT_API_KEY must be set in production!")
            if self.debug:
                logger.warning("DEBUG=true in production — consider disabling")

        return self


# Singleton — import từ bất kỳ file nào đều dùng chung
settings = Settings()
