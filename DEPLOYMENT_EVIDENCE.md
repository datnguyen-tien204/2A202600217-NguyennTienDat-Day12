# Deployment Evidence Checklist

## Part 3 - Cloud Deployment

### Target
- [x] Railway public URL: https://2a202600217-nguyenntiendat-day12-production.up.railway.app

### Checklist
- [x] Deploy `03-cloud-deployment/railway/` or `03-cloud-deployment/render/`
- [x] Confirm `/health` returns 200
- [x] Confirm `/ask` responds successfully
- [x] Capture deployment dashboard screenshot
- [x] Capture health check screenshot

### Evidence
- [Railway dashboard screenshot](images/Railway-b3.png)
- [Railway health-check screenshot](images/Railway-b3.png)

### Commands
```bash
curl https://2a202600217-nguyenntiendat-day12-production.up.railway.app/health
curl -X POST https://2a202600217-nguyenntiendat-day12-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```

## Part 5 - Scaling & Reliability

### Target
- [x] Render public URL with Redis: https://scaling-reliability-agent.onrender.com

### Checklist
- [x] Deploy `05-scaling-reliability/render.yaml`
- [x] Confirm Render Redis is connected
- [x] Confirm `/health` returns 200
- [x] Confirm `/ready` returns 200
- [x] Run `test_stateless.py` with the deployed base URL
- [x] Capture deployment dashboard screenshot
- [x] Capture health check screenshot
- [x] Capture `test_stateless.py` output

### Evidence
- [Render dashboard screenshot](images/render-b5.png)
- [Render health-check screenshot](images/render-b5.png)
- [Stateless test output](images/render-b5.png)

### Commands
```bash
set BASE_URL=https://scaling-reliability-agent.onrender.com
python 05-scaling-reliability/production/test_stateless.py
curl https://scaling-reliability-agent.onrender.com/health
curl https://scaling-reliability-agent.onrender.com/ready
```

## What to Put in the Report

1. The final public URL for Part 3.
2. The final public URL for Part 5.
3. Two screenshots for each deployment.
4. The output of the stateless test for Part 5.