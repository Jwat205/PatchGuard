import json
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

_producer: KafkaProducer | None = None


def _get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        kwargs: dict = {
            "bootstrap_servers": settings.kafka_brokers.split(","),
            "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
            "key_serializer": lambda k: k.encode("utf-8") if k else None,
            "retries": 3,
            "acks": "all",
        }
        if settings.kafka_username and settings.kafka_password:
            kwargs.update(
                {
                    "security_protocol": "SASL_SSL",
                    "sasl_mechanism": "SCRAM-SHA-256",
                    "sasl_plain_username": settings.kafka_username,
                    "sasl_plain_password": settings.kafka_password,
                }
            )
        _producer = KafkaProducer(**kwargs)
    return _producer


async def publish_pr_event(event: dict[str, Any]) -> None:
    """Publish a PR event to the Kafka pr-events topic (sync call wrapped for async context)."""
    try:
        producer = _get_producer()
        key = f"{event.get('repo_full_name')}:{event.get('pr_number')}"
        future = producer.send(settings.kafka_topic_pr_events, key=key, value=event)
        producer.flush(timeout=5)
        logger.info(
            "Event published to Kafka", extra={"topic": settings.kafka_topic_pr_events, "key": key}
        )
    except KafkaError as exc:
        logger.error("Failed to publish event to Kafka", extra={"error": str(exc)})
        raise


def close_producer() -> None:
    global _producer
    if _producer is not None:
        _producer.close()
        _producer = None
