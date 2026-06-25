import asyncio
import json
import signal

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from src.config import settings
from src.consumers.handlers import handle_pr_event
from src.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

_running = True


def _shutdown(signum, frame) -> None:
    global _running
    logger.info("Shutdown signal received")
    _running = False


async def consume() -> None:
    consumer = KafkaConsumer(
        settings.kafka_topic_pr_events,
        bootstrap_servers=settings.kafka_brokers.split(","),
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_interval_ms=300_000,
    )

    logger.info("Kafka consumer started", extra={"topic": settings.kafka_topic_pr_events})

    try:
        while _running:
            records = consumer.poll(timeout_ms=1000)
            for tp, messages in records.items():
                for message in messages:
                    try:
                        logger.info("Processing event", extra={"offset": message.offset})
                        await handle_pr_event(message.value)
                        consumer.commit()
                    except Exception as exc:
                        logger.error("Failed to process message", extra={"error": str(exc), "offset": message.offset})
    except KafkaError as exc:
        logger.error("Kafka consumer error", extra={"error": str(exc)})
    finally:
        consumer.close()
        logger.info("Kafka consumer stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    asyncio.run(consume())
