"""Central configuration for every NeuroPit backend service.

Each setting reads from environment variables with safe local defaults so that
the platform boots end to end on a developer machine while still allowing
production overrides via a `.env` file or container environment.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NeuroPitSettings(BaseSettings):
    """Runtime configuration shared by every backend process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Streaming
    kafka_broker_url: str = Field(default="localhost:9092")
    kafka_internal_url: str = Field(default="redpanda:29092")

    # Influx
    influxdb_url: str = Field(default="http://localhost:8086")
    influxdb_token: str = Field(default="neuropit-local-dev-token-999")
    influxdb_org: str = Field(default="neuropit")
    influxdb_bucket: str = Field(default="neuropit-telemetry")

    # Qdrant
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str = Field(default="")

    # IBM Granite (local Hugging Face by default, watsonx as cloud fallback)
    granite_model_id: str = Field(default="ibm-granite/granite-3.1-8b-instruct")
    granite_use_local: bool = Field(default=True)
    granite_use_stub: bool = Field(default=False)
    watsonx_api_key: str = Field(default="")
    watsonx_project_id: str = Field(default="")
    watsonx_url: str = Field(default="https://us-south.ml.cloud.ibm.com")

    # Langflow
    langflow_api_url: str = Field(default="http://localhost:7860")

    # API gateway
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_jwt_secret: str = Field(default="neuropit-dev-jwt-secret-change-me")
    api_jwt_algorithm: str = Field(default="HS256")
    api_token_expiry_minutes: int = Field(default=120)

    # Privacy
    audit_log_dir: str = Field(default="./audit_logs")
    biometric_retention_hours: int = Field(default=24)
    encryption_key: str = Field(default="")

    # Playback defaults
    default_playback_year: int = Field(default=2021)
    default_playback_event: str = Field(default="Abu Dhabi")
    default_playback_session: str = Field(default="R")
    default_playback_drivers: str = Field(default="VER,HAM")
    default_playback_speed: float = Field(default=2.0)

    def playback_driver_list(self) -> List[str]:
        return [d.strip() for d in self.default_playback_drivers.split(",") if d.strip()]


@lru_cache(maxsize=1)
def get_settings() -> NeuroPitSettings:
    """Return a process wide cached settings instance."""
    return NeuroPitSettings()
