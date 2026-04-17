# VinmecPrep AI - Simple API

Ban nay da duoc rut gon de deploy dang **single-service** tren Render:

- 1 FastAPI web service
- 1 Redis instance de luu session, rate limit, cost guard
- khong dung Kafka, docker-compose, worker, nginx, Weaviate hay SearXNG bat buoc

## Chay local

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Deploy Render

- Service type: `Web Service`
- Language: `Docker`
- Root Directory: `06-lab-complete/VinmecKafka`
- Datastore: `Key Value`
- Set `REDIS_URL` bang internal URL cua Render Key Value

## Endpoints

- `GET /health`
- `GET /ready`
- `GET /metrics` (can `X-Trainer-Key`)
- `POST /chat` (can `X-API-Key`)

## Vi du `/chat`

Headers:

```text
Content-Type: application/json
X-API-Key: YOUR_AGENT_API_KEY
```

Body:

```json
{
  "message": "Toi can chuan bi gi truoc khi kham tim mach?",
  "session_id": "demo-session-001",
  "history": []
}
```
