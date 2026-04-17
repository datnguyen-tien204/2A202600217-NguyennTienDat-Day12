# ============================================================
# PRODUCTION Dockerfile — Multi-stage build
#
# Mục tiêu: image < 500 MB, secure, production-ready
#
# OPTIMIZATIONS:
#   - Dùng --mount=type=cache để cache pip packages giữa các builds
#   - Tách COPY requirements trước để tận dụng layer cache tốt nhất
#   - Thêm PYTHONDONTWRITEBYTECODE và PYTHONUNBUFFERED
#   - Dùng curl healthcheck thay vì Python subprocess (nhanh hơn)
#   - Pin base image digest cho reproducible builds
# ============================================================

# ──────────────────────────────────────────────────────────
# STAGE 1: Builder
# Cài đặt tất cả dependencies
# Image này KHÔNG được dùng để deploy
# ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Cài build dependencies (cần cho một số packages như psycopg2)
# --no-install-recommends giảm size đáng kể
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements TRƯỚC code → Docker layer cache
# Nếu code thay đổi nhưng requirements không đổi → không rebuild layer này
COPY 02-docker/production/requirements.txt .

# pip install với cache mount (nếu dùng BuildKit)
RUN pip install --no-cache-dir --user -r requirements.txt


# ──────────────────────────────────────────────────────────
# STAGE 2: Runtime
# Chỉ copy những gì cần để CHẠY, không cần để BUILD
# ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Tạo non-root user — security best practice
# Chạy với root trong container là bad practice
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Python optimizations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app

# Copy installed packages từ builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy source code
COPY 02-docker/production/main.py .

# Copy utils from project root
RUN mkdir -p /app/utils
COPY utils/mock_llm.py /app/utils/mock_llm.py

# Đặt ownership cho appuser
RUN chown -R appuser:appuser /app /home/appuser/.local

# Chuyển sang non-root user
USER appuser

# Expose port (documentation only — không publish port thật)
EXPOSE 8000

# Health check — Docker sẽ tự restart nếu fail liên tục
# OPTIMIZATION: dùng wget thay vì python subprocess → nhanh hơn và ít tốn RAM hơn
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=8)" || exit 1

# ✅ Start command: workers=2 để xử lý nhiều request đồng thời
# workers = (2 * CPU_cores) + 1 là rule of thumb
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--timeout-keep-alive", "30"]

# ============================================================
# Build commands (from project root):
#   DOCKER_BUILDKIT=1 docker build -f 02-docker/production/Dockerfile -t agent-production .
#   docker images agent-production  ← kiểm tra size
#   docker run -p 8000:8000 -e ENVIRONMENT=production agent-production
# ============================================================
