from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "patchguard"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # GitHub
    github_token: str = ""
    github_webhook_secret: str = ""

    # LLM
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://patchguard:patchguard@localhost:5432/patchguard"
    postgres_user: str = "patchguard"
    postgres_password: str = "patchguard"
    postgres_db: str = "patchguard"

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "patchguard"

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_ttl_seconds: int = 3600

    # Kafka
    kafka_brokers: str = "localhost:9092"
    kafka_topic_pr_events: str = "pr-events"
    kafka_topic_review_results: str = "review-results"
    kafka_consumer_group: str = "patchguard-consumers"

    # API
    host: str = "0.0.0.0"
    port: int = 8000

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_asyncpg_driver(cls, v: str) -> str:
        """Coerce postgresql:// to postgresql+asyncpg:// for SQLAlchemy."""
        if isinstance(v, str):
            v = v.replace("postgres://", "postgresql://", 1)
            if v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # OpenTelemetry
    otel_service_name: str = "patchguard"
    otel_exporter_jaeger_endpoint: str = "http://localhost:14268/api/traces"


settings = Settings()
