# Deployment Evidence Checklist

## Part 3 - Cloud Deployment

### Target
- [x] Railway public URL: https://2a202600217-nguyenntiendat-day12-production.up.railway.app

### Checklist
- [ ] Deploy `03-cloud-deployment/railway/` or `03-cloud-deployment/render/`
- [ ] Confirm `/health` returns 200
- [ ] Confirm `/ask` responds successfully
- [ ] Capture deployment dashboard screenshot
- [ ] Capture health check screenshot

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
- [ ] Deploy `05-scaling-reliability/render.yaml`
- [ ] Confirm Render Redis is connected
- [ ] Confirm `/health` returns 200
- [ ] Confirm `/ready` returns 200
- [ ] Run `test_stateless.py` with the deployed base URL
- [ ] Capture deployment dashboard screenshot
- [ ] Capture health check screenshot
- [ ] Capture `test_stateless.py` output

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