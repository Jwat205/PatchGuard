from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from prometheus_client import Counter, Histogram, make_asgi_app

from src.config import settings

webhook_counter = Counter("patchguard_webhooks_total", "Total GitHub webhooks received")

latency_histogram = Histogram(
    "patchguard_review_latency_seconds",
    "End-to-end review latency in seconds",
    buckets=(1, 5, 10, 15, 20, 25, 30, 45, 60, 120),
)

validation_counter = Counter(
    "patchguard_llm_validations_passed_total",
    "Agent responses that passed schema validation",
)

validation_failure_counter = Counter(
    "patchguard_llm_validations_failed_total",
    "Agent responses that failed schema validation",
)

cache_hits = Counter("patchguard_cache_hits_total", "Redis cache hits")
cache_misses = Counter("patchguard_cache_misses_total", "Redis cache misses")

secret_detections = Counter(
    "patchguard_secret_detections_total",
    "Secrets detected by scanner",
    ["detection_type"],
)

metrics_app = make_asgi_app()


def setup_tracing() -> trace.Tracer:
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(settings.otel_service_name)


tracer = setup_tracing()
