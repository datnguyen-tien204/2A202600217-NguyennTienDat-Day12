# Deployment Evidence Checklist

## Part 3 - Cloud Deployment

### Target
- [ ] Railway or Render public URL

### Checklist
- [ ] Deploy `03-cloud-deployment/railway/` or `03-cloud-deployment/render/`
- [ ] Confirm `/health` returns 200
- [ ] Confirm `/ask` responds successfully
- [ ] Capture deployment dashboard screenshot
- [ ] Capture health check screenshot

### Commands
```bash
curl https://YOUR-PART-3-URL/health
curl -X POST https://YOUR-PART-3-URL/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```

## Part 5 - Scaling & Reliability

### Target
- [ ] Render public URL with Redis

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
set BASE_URL=https://YOUR-PART-5-URL
python 05-scaling-reliability/production/test_stateless.py
curl https://YOUR-PART-5-URL/health
curl https://YOUR-PART-5-URL/ready
```

## What to Put in the Report

1. The final public URL for Part 3.
2. The final public URL for Part 5.
3. Two screenshots for each deployment.
4. The output of the stateless test for Part 5.