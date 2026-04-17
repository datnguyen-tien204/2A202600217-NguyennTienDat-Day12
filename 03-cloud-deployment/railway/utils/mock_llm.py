"""
Mock LLM — dùng chung cho tất cả ví dụ.
Không cần API key thật. Trả lời giả lập để focus vào deployment concept.

Optimizations:
  - Thêm async version để không block event loop
  - Thêm more realistic responses
  - Loại bỏ random delay noise không cần thiết
"""
import asyncio
import time
import random

MOCK_RESPONSES = {
    "default": [
        "Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.",
        "Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.",
        "Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận và xử lý.",
        "Câu hỏi hay! Trong production, tôi sẽ gọi OpenAI/Anthropic API để trả lời chính xác hơn.",
    ],
    "docker": [
        "Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!",
        "Docker giúp đảm bảo app chạy giống nhau trên mọi môi trường: dev, staging, production.",
    ],
    "deploy": [
        "Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được.",
        "CI/CD pipeline giúp tự động hóa quá trình test → build → deploy.",
    ],
    "health": [
        "Agent đang hoạt động bình thường. All systems operational.",
        "Health check OK. Service is running smoothly.",
    ],
    "scale": [
        "Horizontal scaling: chạy nhiều instances để handle nhiều traffic hơn.",
        "Stateless design + Redis session cho phép scale không giới hạn.",
    ],
    "redis": [
        "Redis là in-memory store cực nhanh, dùng cho session, cache, rate limiting.",
        "Redis pub/sub và streams rất hữu ích cho real-time features.",
    ],
    "security": [
        "JWT token giúp xác thực stateless, không cần lưu session trên server.",
        "Rate limiting và cost guard bảo vệ service khỏi abuse và bill bất ngờ.",
    ],
    "cloud": [
        "Cloud Run tự động scale to zero khi không có traffic — tiết kiệm chi phí.",
        "Railway và Render cực dễ deploy: chỉ cần push code lên GitHub.",
    ],
}


def ask(question: str, delay: float = 0.1) -> str:
    """
    Mock LLM call (synchronous).
    Simulate API latency với fixed delay.
    """
    time.sleep(delay)

    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)

    return random.choice(MOCK_RESPONSES["default"])


async def ask_async(question: str, delay: float = 0.1) -> str:
    """
    Mock LLM call (asynchronous).
    Dùng asyncio.sleep thay vì time.sleep để không block event loop.
    """
    await asyncio.sleep(delay)

    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)

    return random.choice(MOCK_RESPONSES["default"])


def ask_stream(question: str):
    """
    Mock streaming response — yield từng token.
    """
    response = ask(question, delay=0.05)
    words = response.split()
    for i, word in enumerate(words):
        time.sleep(0.04)
        yield word + (" " if i < len(words) - 1 else "")
