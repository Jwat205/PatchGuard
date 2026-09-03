# PatchGuard

Autonomous GitHub pull request review service. When a PR is opened or updated, PatchGuard fetches the diff, runs it through three specialized AI agents, and posts a structured review back to the PR — security findings, dependency risks, and code quality issues — in under 10 seconds.

## How it works

GitHub sends a webhook to PatchGuard when a PR is opened or updated. The event is queued via Celery (Redis broker on Upstash), then the orchestrator runs the diff through the review pipeline and posts results back to GitHub. If Celery is unavailable, the review runs as a FastAPI background task in-process.

```
GitHub PR → webhook → Celery task (Redis) → orchestrator → 3 AI agents → GitHub review comment
                            ↓ (fallback if Redis down)                  ↓
                    FastAPI BackgroundTask               PostgreSQL (reviews + findings)
                                                        DynamoDB   (audit log)
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
| DynamoDB | aioboto3 (async) — append-only event audit log |
| Observability | Prometheus counters/histograms + OpenTelemetry traces |
| Hosting | AWS EC2 (Docker, free tier) |
| CI/CD | GitHub Actions → ECR → SSM Run Command deploy to EC2 |

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
docker compose up -d          # PostgreSQL, Redis, DynamoDB Local
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
| PostgreSQL | [RDS](https://aws.amazon.com/rds/) `db.t3.micro` | PR reviews, individual findings |
| Redis | [ElastiCache](https://aws.amazon.com/elasticache/) `cache.t3.micro` | Diff cache + Celery task queue |
| Audit log | [DynamoDB](https://aws.amazon.com/dynamodb/) | Append-only PR/review event log |
| Hosting | [EC2](https://aws.amazon.com/ec2/) `t3.micro` (Docker) | Web service |
| Image registry | [ECR](https://aws.amazon.com/ecr/) | Docker images |

Provisioned by `scripts/provision_aws.py` (torn down by `scripts/teardown_aws.py`) - see that
script's docstring for what it creates and why.

## Deployment

The service runs on an EC2 instance as a single Docker container, in a VPC alongside RDS and
ElastiCache (both private - reachable only from that instance's security group).

1. Push to `main` → GitHub Actions runs the test suite
2. On success, Actions builds the Docker image and pushes it to ECR
3. Actions calls the AWS API (SSM Run Command) to tell the EC2 instance to pull the new image
   and restart the container - no SSH connection from the runner, ever

Required GitHub Actions secrets (repo Settings → Secrets and variables → Actions):

```
AWS_ACCESS_KEY_ID      IAM user with ecr:*, ssm:SendCommand, ssm:GetCommandInvocation, ec2:DescribeInstances
AWS_SECRET_ACCESS_KEY  (secret key for that user)
```

The app's runtime env vars (`DATABASE_URL`, `REDIS_URL`, `AWS_REGION`, `GITHUB_TOKEN`,
`GITHUB_WEBHOOK_SECRET`, `JWT_SECRET_KEY`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`) live in
`/opt/patchguard/.env` on the EC2 instance itself, not in GitHub Actions - the deploy step only
pulls and restarts the container, it never carries secrets through CI. Set that file up once
after provisioning (values come from `scripts/aws-provision-output.json` and the RDS/
ElastiCache console pages for their endpoints).

## GitHub App setup

1. Go to GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App
2. Set webhook URL to `http://<ec2-public-ip>/github/webhook` (or a domain pointed at it)
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
  db/           database.py (PostgreSQL), redis_client.py, dynamodb.py
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
