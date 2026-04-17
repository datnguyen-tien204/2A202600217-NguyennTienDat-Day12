# Day 12 Lab - Mission Answers

## Submission Scope

1. Part 1, Part 2, and Part 4 are local code/explanation parts.
2. Part 3 requires a public deployment on Railway or Render.
3. Part 5 requires a public deployment on Render with Redis.
4. The final combined project in `06-lab-complete` is the reference implementation.

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Hardcoded secrets or config in code.
2. Missing health and readiness endpoints.
3. No graceful shutdown handling.
4. Dev-only settings mixed into production code.

### Exercise 1.2: Production improvements
1. Read config from environment variables.
2. Expose `/health` and `/ready`.
3. Use structured logging.
4. Bind to `0.0.0.0` and honor `PORT`.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why it matters |
|---------|---------|------------|----------------|
| Config | Hardcoded / local defaults | Env-based config | Safer and easier to deploy |
| Health check | Missing | `/health` | Platform can restart unhealthy app |
| Readiness | Missing | `/ready` | Prevents early traffic routing |
| Shutdown | Abrupt | Graceful | Avoids dropped requests |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: `python:3.11-slim`.
2. Working directory: `/app` in the runtime stage.
3. Multi-stage build keeps the final image smaller and cleaner.

### Exercise 2.2: Compose stack
1. The API service runs behind Nginx.
2. Redis stores shared state and supports session or cache use cases.
3. Kafka is initialized before the API and consumer start.

### Exercise 2.3: Image size comparison
1. The develop image is simpler but not production-focused.
2. The production image removes build tools and keeps only runtime dependencies.
3. The final production image is much smaller than the basic one.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway / Render deployment
1. Render blueprint: `03-cloud-deployment/render/render.yaml`.
2. Render app entrypoint: `03-cloud-deployment/render/app.py`.
3. Render dependencies: `03-cloud-deployment/render/requirements.txt`.
4. Railway example: `03-cloud-deployment/railway/`.

### Exercise 3.2: Cloud readiness
1. Use `PORT` from the platform.
2. Provide `/health` for uptime and status.
3. Keep the service stateless so it can scale safely.

### Evidence to attach
1. Public URL for Part 3.
2. Screenshot of the deployment dashboard.
3. Screenshot of the health check response.

## Part 4: API Security

### Exercise 4.1-4.3: Test results
1. API key or JWT protects the main endpoint.
2. Rate limiting blocks excessive traffic.
3. Cost guard stops requests when the budget is exceeded.

### Exercise 4.4: Cost guard implementation
1. Track per-user usage.
2. Track global usage.
3. Reset the global budget each day.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
1. The service is stateless because session data is stored in Redis.
2. `test_stateless.py` can use any base URL through `BASE_URL`.
3. Production mode requires Redis through `REQUIRE_REDIS=true`.
4. A Render blueprint is provided in `05-scaling-reliability/render.yaml`.
5. `/health` and `/ready` are exposed for cloud checks.
6. Docker Compose remains the local scale demo; Render uses the web service plus Redis add-on.

### Evidence to attach
1. Public Render URL for Part 5.
2. Screenshot of the Render deployment dashboard.
3. Screenshot of the `/health` endpoint.
4. Output of `test_stateless.py` showing the stateless behavior.

## Final Notes

1. Part 3 is the Railway/Render deployment exercise.
2. Part 5 is the Render deployment exercise I would submit for the public URL requirement.
3. Part 1, 2, and 4 are documented and implemented locally.