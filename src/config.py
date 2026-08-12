import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """集中定义应用运行配置，并支持通过环境变量覆盖默认值。"""

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
    LLM_MODEL_NAME: Optional[str] = Field(default=None)
    PROMPT_VERSION: str = Field(default="support-v1")
    AGENT_WORKFLOW_VERSION: str = Field(default="support-workflow-v1")
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None)
    AZURE_OPENAI_API_VERSION: Optional[str] = Field(default="2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = Field(default="gpt-4")

    # Vector DB
    VECTOR_DB_PERSIST_DIR: str = Field(default="./chromadb_store")
    CHROMA_HOST: Optional[str] = Field(default=None)
    CHROMA_PORT: Optional[int] = Field(default=None)

    # Observability：应用仅通过 OpenTelemetry SDK 采集并使用 OTLP 导出。
    OTEL_ENABLED: bool = Field(default=True)
    OTEL_SERVICE_NAME: str = Field(default="supportgpt-backend")
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: Optional[str] = Field(default=None)
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: Optional[str] = Field(default=None)
    OTEL_METRIC_EXPORT_INTERVAL_MILLISECONDS: int = Field(default=15000, ge=1000)
    OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS: float = Field(default=3.0)
    OTEL_CONSOLE_EXPORTER: bool = Field(default=False)
    OTEL_TRACE_SAMPLE_RATIO: float = Field(default=1.0, ge=0.0, le=1.0)
    OTEL_EXCLUDED_URLS: str = Field(default="health")
    # 仅用于共享 .env 校验和 Collector 容器替换，业务代码不会使用或直连。
    OTEL_COLLECTOR_LANGSMITH_API_KEY: Optional[str] = Field(default=None)
    OTEL_COLLECTOR_LANGSMITH_PROJECT: str = Field(default="supportgpt-enterprise")
    OTEL_COLLECTOR_LANGSMITH_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com/otel/v1/traces"
    )

    # Guardrails Settings
    PII_ANONYMIZATION_ENABLED: bool = Field(default=True)
    PROMPT_INJECTION_PROTECTION_ENABLED: bool = Field(default=True)
    JAILBREAK_DETECTION_ENABLED: bool = Field(default=True)
    RESPONSE_FILTERING_ENABLED: bool = Field(default=True)

    # Feedback Pipeline
    FEEDBACK_TRAINING_MIN_RATING: int = Field(default=4, ge=1, le=5)
    FEEDBACK_TRAINING_MIN_QA_SCORE: float = Field(default=0.8, ge=0.0, le=1.0)
    FEEDBACK_TRAINING_MIN_RAG_SCORE: float = Field(default=0.75, ge=0.0, le=1.0)

    class Config:
        """定义 Pydantic Settings 读取 `.env` 的规则。"""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
