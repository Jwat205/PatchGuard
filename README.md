# PatchGuard

Autonomous GitHub pull request review service. When a PR is opened or updated, PatchGuard fetches the diff, runs it through three specialized AI agents, and posts a structured review back to the PR — security findings, dependency risks, and code quality issues — in under 10 seconds.

## How it works

GitHub sends a webhook to PatchGuard when a PR is opened or updated. The event is queued via Celery (Redis broker on Upstash), then the orchestrator runs the diff through the review pipeline and posts results back to GitHub. If Celery is unavailable, the review runs as a FastAPI background task in-process.

```
GitHub PR → webhook → Celery task (Redis) → orchestrator → 3 AI agents → GitHub review comment
                            ↓ (fallback if Redis down)                  ↓
                    FastAPI BackgroundTask               PostgreSQL (reviews + findings)
                                                        MongoDB    (audit log)
                                                        Redis      (diff cache)
                                                        Prometheus (/metrics)
```

**Three agents run on every PR:**

- **Quality** — missing tests, N+1 queries, poor naming, excessive complexity
- **Security** — JWT flaws, SQL injection, exposed secrets, CORS misconfiguration
- **Dependency** — unpinned versions, packages with CVEs, typosquatting risks

A regex + Shannon entropy secret scanner runs before the agents (no LLM needed) and feeds its findings into the Security Agent prompt.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI (async) |
| Queue | Celery + Redis (Upstash) |
| LLM | OpenAI-compatible — Ollama locally, Groq in production |
| PostgreSQL | Neon (free tier) — stores reviews and findings |
| Redis | Upstash (free tier) — caching + Celery broker |
| MongoDB | Motor (async) — append-only event audit log |
| Observability | Prometheus counters/histograms + OpenTelemetry traces |
| Hosting | Render (Docker, free tier) |
| CI/CD | GitHub Actions → ghcr.io → Render deploy hook |

## Local setup

**Requirements:** Python 3.11+, Docker (for local services)

```bash
git clone https://github.com/Jwat205/PatchGuard.git
cd PatchGuard
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — minimum required fields:

```env
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=any-random-string
JWT_SECRET_KEY=any-random-string-32-chars
DATABASE_URL=postgresql://... (Neon)
REDIS_URL=rediss://...       (Upstash)
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5-coder:7b
```

Start local services and run:

```bash
docker compose up -d          # PostgreSQL, Redis, MongoDB
uvicorn src.main:app --reload
```

Run tests:

```bash
pytest tests/ -q
```

Tests use in-memory SQLite and fakeredis — no external services needed.

## LLM options

Switch providers by changing three env vars — no code changes:

| Provider | Cost | LLM_BASE_URL | LLM_API_KEY | LLM_MODEL |
|---|---|---|---|---|
| Ollama (local) | Free | `http://localhost:11434/v1` | `ollama` | `qwen2.5-coder:7b` |
| Groq (hosted) | Free tier | `https://api.groq.com/openai/v1` | Groq API key | `llama-3.1-8b-instant` |

Get a Groq API key at [console.groq.com](https://console.groq.com).

For Ollama: install from [ollama.com](https://ollama.com), then `ollama pull qwen2.5-coder:7b`.

## Cloud services (free tier)

| Service | Provider | What it stores |
|---|---|---|
| PostgreSQL | [Neon](https://neon.tech) | PR reviews, individual findings |
| Redis | [Upstash](https://upstash.com) | Diff cache + Celery task queue |
| Hosting | [Render](https://render.com) | Web service (Docker) |

## Deployment

The service runs on Render as a Docker container (`python:3.11-slim`).

1. Push to `main` → GitHub Actions runs the test suite
2. On success, Actions triggers the Render deploy hook
3. Render pulls the new image and restarts the service

Configure these env vars in the Render dashboard (Environment tab):

```
DATABASE_URL          postgresql://... (Neon)
REDIS_URL             rediss://...     (Upstash)
MONGODB_URL           mongodb+srv://...
GITHUB_TOKEN          ghp_...
GITHUB_WEBHOOK_SECRET (same value as your GitHub App webhook secret)
JWT_SECRET_KEY        (random 32+ char string)
LLM_BASE_URL          https://api.groq.com/openai/v1
LLM_API_KEY           (Groq API key)
LLM_MODEL             llama-3.1-8b-instant
APP_ENV               production
```

## GitHub App setup

1. Go to GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App
2. Set webhook URL to `https://patchguard.onrender.com/github/webhook`
3. Set webhook secret to match `GITHUB_WEBHOOK_SECRET`
4. Repository permissions: **Contents** read, **Pull requests** read+write
5. Subscribe to: **Pull request** events
6. Install the app on your repository

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/github/webhook` | Receives GitHub PR events |
| `GET` | `/health` | Service health + DB/Redis connectivity |
| `GET` | `/reviews/{id}` | Fetch a completed review (JWT required) |
| `GET` | `/reviews/` | Paginated review history (JWT required) |
| `GET` | `/metrics` | Prometheus metrics |

## Metrics

Live metrics at `/metrics`. Key queries:

```promql
# Review latency P95
histogram_quantile(0.95, patchguard_review_latency_seconds_bucket)

# Agent validation pass rate
rate(patchguard_llm_validations_passed_total[5m])
/ (rate(patchguard_llm_validations_passed_total[5m]) + rate(patchguard_llm_validations_failed_total[5m]))

# Cache hit rate
rate(patchguard_cache_hits_total[5m])
/ (rate(patchguard_cache_hits_total[5m]) + rate(patchguard_cache_misses_total[5m]))
```

Historical data in Neon:

```sql
-- Total reviews processed
SELECT COUNT(*) FROM pull_requests WHERE status = 'success';

-- P95 latency
SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) / 1000.0 AS p95_seconds
FROM pull_requests WHERE status = 'success';

-- Findings by severity
SELECT severity, COUNT(*) FROM findings GROUP BY severity;
```

## Project structure

```
src/
  api/          webhooks.py, reviews.py, health.py
  agents/       base_agent.py, quality_agent.py, security_agent.py, dependency_agent.py
  consumers/    handlers.py, celery_tasks.py
  db/           database.py (PostgreSQL), redis_client.py, mongodb.py
  models/       postgres_models.py (ORM), schemas.py (Pydantic)
  services/     orchestrator.py, secret_scanner.py, cache_service.py,
                event_store.py, github_service.py, monitoring.py
  utils/        logging.py, validators.py, cache_keys.py
  auth.py       JWT generation and verification
  config.py     All settings via pydantic-settings
tests/
  test_agents/  test_quality_agent.py, test_security_agent.py, test_dependency_agent.py
  test_api/     test_webhooks.py, test_reviews.py, test_health.py
  test_services/ test_orchestrator.py, test_cache_service.py, test_secret_scanner.py
  integration/  test_end_to_end.py
```

## License

MIT
