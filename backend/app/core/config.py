"""
Application configuration using Pydantic Settings v2.
All configuration is read from environment variables / .env file.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Repo root: .../backend/app/core/config.py -> up four parents.
# Anchoring here keeps the .env file and the dev SQLite database on the same
# files no matter which directory the process was launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """
    All application settings.

    Values are loaded from environment variables. The .env file is
    automatically read when present. See .env.example for documentation
    of each variable.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    APP_NAME: str = "Autonomous Engineering Intelligence Platform"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-to-a-random-64-char-secret-key"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Database ───────────────────────────────────────────────────────────
    # Set false to create investigations without executing the workflow
    # (tests, seeding, and bulk imports that should not spend LLM budget).
    AUTO_LAUNCH_INVESTIGATIONS: bool = True

    DATABASE_URL: str = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'aeip_dev.db'}"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = "fake://"

    # ── Qdrant ────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_PREFIX: str = "aeip"

    # ── Object Storage ────────────────────────────────────────────────────
    STORAGE_PROVIDER: Literal["minio", "s3", "local"] = "local"
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_ACCESS_KEY: str = "aeip_minio"
    STORAGE_SECRET_KEY: str = "aeip_minio_secret"
    STORAGE_BUCKET: str = "aeip-artifacts"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_LOCAL_PATH: str = "./investigation_artifacts"

    # ── LLM ───────────────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["openai", "anthropic", "gemini", "ollama"] = "openai"
    LLM_MODEL: str = "gpt-4o"
    LLM_FAST_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = Field(default=0.1, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(default=4096, ge=100)
    LLM_TIMEOUT_SECONDS: int = 120

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Gemini
    GEMINI_API_KEY: str = ""

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Budget Controls ────────────────────────────────────────────────────
    INVESTIGATION_MAX_TOKENS: int = 500_000
    INVESTIGATION_MAX_TOOL_CALLS: int = 200
    INVESTIGATION_MAX_DURATION_SECONDS: int = 3600
    INVESTIGATION_MAX_RETRIES: int = 3

    # ── Authentication ─────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Observability ──────────────────────────────────────────────────────
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "aeip-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "grpc"
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    # ── Sandbox ────────────────────────────────────────────────────────────
    SANDBOX_PROVIDER: Literal["docker", "subprocess"] = "subprocess"
    SANDBOX_IMAGE: str = "aeip-sandbox:latest"
    SANDBOX_CPU_LIMIT: str = "1.0"
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_TIMEOUT_SECONDS: int = 60
    SANDBOX_NETWORK_DISABLED: bool = True

    # ── Git ────────────────────────────────────────────────────────────────
    GIT_WORKSPACE_PATH: str = "./git_workspaces"
    GIT_MAX_DIFF_LINES: int = 10_000
    GIT_CLONE_TIMEOUT_SECONDS: int = 120

    # ── Investigation Defaults ─────────────────────────────────────────────
    INVESTIGATION_DEFAULT_PRIORITY: str = "medium"
    INVESTIGATION_CHECKPOINT_ENABLED: bool = True
    INVESTIGATION_PARALLEL_TASKS_MAX: int = 5

    # ── Approval Gates ─────────────────────────────────────────────────────
    REQUIRE_APPROVAL_FOR_PATCH: bool = True
    REQUIRE_APPROVAL_FOR_BRANCH: bool = True
    REQUIRE_APPROVAL_FOR_PR: bool = True

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_INVESTIGATIONS_PER_HOUR: int = 10

    # ── Computed fields ────────────────────────────────────────────────────

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS from comma-separated string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @computed_field
    @property
    def is_sqlite(self) -> bool:
        """Whether the database is SQLite (dev mode)."""
        return "sqlite" in self.DATABASE_URL.lower()

    @computed_field
    @property
    def is_fake_redis(self) -> bool:
        """Whether we are using fakeredis (dev mode)."""
        return self.REDIS_URL.startswith("fake://")

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = {"openai", "anthropic", "gemini", "ollama"}
        if v not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of: {allowed}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


# Global settings instance
settings = get_settings()
