"""Bootstrap script for the local NeuroPit infrastructure.

Creates every Kafka topic listed in `docs/EVENT_TAXONOMY.md` and every Qdrant
collection the reasoning layer expects. Safe to run repeatedly. Existing
topics and collections are skipped without error.
"""

from __future__ import annotations

import logging
import time

from confluent_kafka.admin import AdminClient, NewTopic
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from src.backend.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


REQUIRED_TOPICS = [
    "incoming-telemetry-raw",
    "telemetry-features",
    "biometrics-enriched",
    "cognitive-state-inference",
    "explanation-events",
    "incoming-race-events",
    "anomaly-events",
    "stress-events",
    "overtake-events",
    "emotional-events",
    "weather-events",
    "strategy-events",
    "simulation-events",
]

QDRANT_COLLECTIONS = {
    "motorsport_ontology": 768,
    "historical_telemetry_vectors": 768,
    "cognitive_state_memory": 768,
}


def init_kafka_topics() -> None:
    settings = get_settings()
    logger.info("Initialising Kafka event topics on %s", settings.kafka_broker_url)
    admin_client = AdminClient({"bootstrap.servers": settings.kafka_broker_url})
    existing_topics = admin_client.list_topics(timeout=10).topics

    topics_to_create = [
        NewTopic(topic, num_partitions=3, replication_factor=1)
        for topic in REQUIRED_TOPICS
        if topic not in existing_topics
    ]

    if not topics_to_create:
        logger.info("All Kafka topics already present")
        return

    fs = admin_client.create_topics(topics_to_create)
    for topic, future in fs.items():
        try:
            future.result()
            logger.info("Topic %s created", topic)
        except Exception as exc:
            logger.error("Failed to create topic %s: %s", topic, exc)


def init_qdrant_collections() -> None:
    settings = get_settings()
    logger.info("Initialising Qdrant collections at %s:%d", settings.qdrant_host, settings.qdrant_port)
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    existing = {c.name for c in client.get_collections().collections}
    for name, vector_size in QDRANT_COLLECTIONS.items():
        if name in existing:
            logger.info("Qdrant collection %s already exists", name)
            continue
        try:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("Qdrant collection %s created", name)
        except Exception as exc:
            logger.error("Failed to create Qdrant collection %s: %s", name, exc)


def main() -> None:
    logger.info("Waiting for infrastructure services to come online")
    time.sleep(10)
    init_kafka_topics()
    init_qdrant_collections()
    logger.info("Infrastructure initialisation complete")


if __name__ == "__main__":
    main()
