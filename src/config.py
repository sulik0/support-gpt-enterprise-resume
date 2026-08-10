import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # API Settings
    APP_NAME: str = Field(default="SupportGPT-Enterprise")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    PORT: int = Field(default=8000)
    HOST: str = Field(default="0.0.0.0")

    # Security & Auth
    JWT_SECRET: str = Field(default="super-secret-jwt-key-change-in-production-123456")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # Database & Cache
    # Default to sqlite in-memory or file for easy local run without postgres, override via env
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./supportgpt.db")
    REDIS_URL: Optional[str] = Field(default=None)

    # LLM Configuration
    LLM_PROVIDER: str = Field(default="mock")  # mock, openai, azure
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None)
    AZURE_OPENAI_API_VERSION: Optional[str] = Field(default="2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = Field(default="gpt-4")

    # Vector DB
    VECTOR_DB_PERSIST_DIR: str = Field(default="./chromadb_store")
    CHROMA_HOST: Optional[str] = Field(default=None)
    CHROMA_PORT: Optional[int] = Field(default=None)

    # Observability
    PROMETHEUS_METRICS_ENABLED: bool = Field(default=True)
    LANGSMITH_TRACING: bool = Field(default=False)
    LANGSMITH_API_KEY: Optional[str] = Field(default=None)
    LANGSMITH_PROJECT: str = Field(default="supportgpt-enterprise")
    LANGSMITH_ENDPOINT: str = Field(default="https://api.smith.langchain.com")
    LANGSMITH_WORKSPACE_ID: Optional[str] = Field(default=None)
    # Legacy LangChain names remain supported for backwards compatibility.
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None)
    LANGCHAIN_PROJECT: str = Field(default="supportgpt-enterprise")

    # OpenTelemetry
    OTEL_ENABLED: bool = Field(default=True)
    OTEL_SERVICE_NAME: str = Field(default="supportgpt-backend")
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: Optional[str] = Field(default=None)
    OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS: float = Field(default=3.0)
    OTEL_CONSOLE_EXPORTER: bool = Field(default=False)
    OTEL_TRACE_SAMPLE_RATIO: float = Field(default=1.0, ge=0.0, le=1.0)
    OTEL_EXCLUDED_URLS: str = Field(default="health,metrics")

    # Guardrails Settings
    PII_ANONYMIZATION_ENABLED: bool = Field(default=True)
    PROMPT_INJECTION_PROTECTION_ENABLED: bool = Field(default=True)
    JAILBREAK_DETECTION_ENABLED: bool = Field(default=True)
    RESPONSE_FILTERING_ENABLED: bool = Field(default=True)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
