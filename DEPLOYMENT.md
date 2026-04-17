# Deployment Information

## What needs deployment

1. Part 3 must be deployed on Railway or Render.
2. Part 5 must be deployed on Render with Redis.
3. Part 1, Part 2, and Part 4 only need code and local/Docker proof.

## Public URLs

- Part 3 URL: https://2a202600217-nguyenntiendat-day12-production.up.railway.app
- Part 5 URL: https://scaling-reliability-agent.onrender.com

## Platform

- Part 3: Railway or Render.
- Part 5: Render.

## Deployment checklist

### Part 3
- [ ] Deploy the app from `03-cloud-deployment/railway/` or `03-cloud-deployment/render/`
- [ ] Open the public URL in a browser
- [ ] Confirm `/health` returns 200
- [ ] Capture a deployment screenshot
- [ ] Capture a health check screenshot

### Part 5
- [ ] Deploy using `05-scaling-reliability/render.yaml`
- [ ] Confirm Redis is attached
- [ ] Confirm `/health` returns 200
- [ ] Confirm `/ready` returns 200
- [ ] Run `test_stateless.py` against the public URL
- [ ] Capture a deployment screenshot
- [ ] Capture a health check screenshot
- [ ] Capture the `test_stateless.py` output

## Environment variables set

- `ENVIRONMENT`
- `REDIS_URL`
- `REQUIRE_REDIS`
- `PORT`
- `ALLOWED_ORIGINS`

## Test commands

### Part 3
```bash
curl https://2a202600217-nguyenntiendat-day12-production.up.railway.app/health
curl -X POST https://2a202600217-nguyenntiendat-day12-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### Part 5
```bash
curl https://scaling-reliability-agent.onrender.com/health
curl https://scaling-reliability-agent.onrender.com/ready
```

## Screenshots to attach

1. Part 3 deployment dashboard.
2. Part 3 health check.
3. Part 5 deployment dashboard.
4. Part 5 health check.

## Notes

1. Part 3 can use either Railway or Render.
2. Part 5 should be on Render because Redis is configured in the blueprint.