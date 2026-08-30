import os
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """集中定义应用运行配置，并支持通过环境变量覆盖默认值。"""

    # API Settings
    APP_NAME: str = Field(default="SupportGPT-Enterprise")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
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
    LLM_BASE_URL: Optional[str] = Field(default=None)
    LLM_API_KEY: Optional[str] = Field(default=None)
    # Analyzer 与 QA 可共用独立的小模型服务，未配置时回退主模型。
    LLM_FAST_MODEL_NAME: Optional[str] = Field(default=None)
    LLM_FAST_BASE_URL: Optional[str] = Field(default=None)
    LLM_FAST_API_KEY: Optional[str] = Field(default=None)
    LLM_ANALYZER_MODEL_NAME: Optional[str] = Field(default=None)
    LLM_QA_MODEL_NAME: Optional[str] = Field(default=None)
    LLM_ANALYZER_MAX_TOKENS: int = Field(default=120, ge=32, le=512)
    LLM_RESOLVER_MAX_TOKENS: int = Field(default=320, ge=64, le=2048)
    LLM_QA_MAX_TOKENS: int = Field(default=96, ge=32, le=512)
    LLM_RESOLVER_MAX_RAG_CHARS: int = Field(default=5000, ge=500, le=20000)
    LLM_RESOLVER_MAX_TOOL_CHARS: int = Field(default=2500, ge=500, le=10000)
    LLM_QA_MAX_CONTEXT_CHARS: int = Field(default=4000, ge=500, le=20000)
    # Resilience 默认只执行一次有界 Retry，避免放大故障。
    RESILIENCE_ENABLED: bool = Field(default=True)
    RESILIENCE_LLM_TIMEOUT_SECONDS: float = Field(default=20.0, gt=0.0)
    RESILIENCE_LLM_MAX_RETRIES: int = Field(default=1, ge=0, le=3)
    RESILIENCE_RAG_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0.0)
    RESILIENCE_RAG_MAX_RETRIES: int = Field(default=1, ge=0, le=3)
    RESILIENCE_TOOL_READ_MAX_RETRIES: int = Field(default=1, ge=0, le=3)
    RESILIENCE_RETRY_BASE_DELAY_SECONDS: float = Field(default=0.1, ge=0.0, le=5.0)
    RESILIENCE_CIRCUIT_FAILURE_THRESHOLD: int = Field(default=3, ge=1, le=20)
    RESILIENCE_CIRCUIT_RECOVERY_SECONDS: float = Field(default=30.0, gt=0.0)
    # 备用模型是可选的 OpenAI-compatible endpoint。
    LLM_FALLBACK_MODEL_NAME: Optional[str] = Field(default=None)
    LLM_FALLBACK_BASE_URL: Optional[str] = Field(default=None)
    LLM_FALLBACK_API_KEY: Optional[str] = Field(default=None)
    PROMPT_VERSION: str = Field(default="support-v1")
    AGENT_WORKFLOW_VERSION: str = Field(default="support-workflow-v1")
    # OPENAI_API_KEY 继续供 Embedding 和离线评测模块独立使用。
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None)
    AZURE_OPENAI_API_VERSION: Optional[str] = Field(default="2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = Field(default="gpt-4")

    # Vector DB
    VECTOR_DB_PERSIST_DIR: str = Field(default="./.runtime/chromadb-0.5")
    CHROMA_HOST: Optional[str] = Field(default=None)
    CHROMA_PORT: Optional[int] = Field(default=None)
    CHROMA_ANONYMIZED_TELEMETRY: bool = Field(default=False)

    # Observability：应用仅通过 OpenTelemetry SDK 采集并使用 OTLP 导出。
    OTEL_ENABLED: bool = Field(default=True)
    OTEL_SERVICE_NAME: str = Field(default="supportgpt-backend")
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: Optional[str] = Field(default=None)
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: Optional[str] = Field(default=None)
    OTEL_METRIC_EXPORT_INTERVAL_MILLISECONDS: int = Field(default=15000, ge=1000)
    OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS: float = Field(default=3.0)
    OTEL_EXPORTER_PREFLIGHT_ENABLED: bool = Field(default=True)
    OTEL_EXPORTER_PREFLIGHT_TIMEOUT_SECONDS: float = Field(
        default=0.25, ge=0.05, le=5.0
    )
    OTEL_CONSOLE_EXPORTER: bool = Field(default=False)
    OTEL_TRACE_SAMPLE_RATIO: float = Field(default=1.0, ge=0.0, le=1.0)
    OTEL_EXCLUDED_URLS: str = Field(default="health")
    # 仅用于共享 .env 校验和 Collector 容器替换，业务代码不会使用或直连。
    OTEL_COLLECTOR_LANGSMITH_API_KEY: Optional[str] = Field(default=None)
    OTEL_COLLECTOR_LANGSMITH_PROJECT: str = Field(default="supportgpt-enterprise")
    OTEL_COLLECTOR_LANGSMITH_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com/otel"
    )
    LANGSMITH_CAPTURE_LLM_CONTENT: bool = Field(default=True)
    LANGSMITH_LLM_CONTENT_MAX_CHARS: int = Field(
        default=50000, ge=1000, le=200000
    )

    # Guardrails Settings
    PII_ANONYMIZATION_ENABLED: bool = Field(default=True)
    PROMPT_INJECTION_PROTECTION_ENABLED: bool = Field(default=True)
    JAILBREAK_DETECTION_ENABLED: bool = Field(default=True)
    RESPONSE_FILTERING_ENABLED: bool = Field(default=True)

    # Qwen3Guard 通过独立 OpenAI-compatible 服务提供语义安全分类。
    QWEN3_GUARD_ENABLED: bool = Field(default=False)
    QWEN3_GUARD_BASE_URL: str = Field(default="http://127.0.0.1:18001/v1")
    QWEN3_GUARD_API_KEY: str = Field(default="EMPTY")
    QWEN3_GUARD_MODEL_NAME: str = Field(default="Qwen/Qwen3Guard-Gen-0.6B")
    QWEN3_GUARD_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0.0)
    QWEN3_GUARD_MAX_RETRIES: int = Field(default=0, ge=0, le=2)
    QWEN3_GUARD_BLOCK_CONTROVERSIAL: bool = Field(default=False)
    QWEN3_GUARD_MAX_INPUT_CHARS: int = Field(default=20000, ge=1000, le=100000)

    # Risk Engine
    RISK_MEDIUM_THRESHOLD: float = Field(default=0.4, ge=0.0, le=1.0)
    RISK_HIGH_THRESHOLD: float = Field(default=0.7, ge=0.0, le=1.0)
    RISK_CRITICAL_THRESHOLD: float = Field(default=0.9, ge=0.0, le=1.0)
    RISK_LOW_CONFIDENCE_THRESHOLD: float = Field(default=0.65, ge=0.0, le=1.0)
    RISK_QA_SCORE_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_risk_thresholds(self):
        """确保风险等级阈值从低到高严格递增。"""
        if not (
            self.RISK_MEDIUM_THRESHOLD
            < self.RISK_HIGH_THRESHOLD
            < self.RISK_CRITICAL_THRESHOLD
        ):
            raise ValueError("Risk thresholds must satisfy medium < high < critical.")
        return self

    @model_validator(mode="after")
    def validate_llm_fallback(self):
        """备用 LLM 三项配置必须同时出现，避免故障时才暴露配置错误。"""
        values = (
            self.LLM_FALLBACK_MODEL_NAME,
            self.LLM_FALLBACK_BASE_URL,
            self.LLM_FALLBACK_API_KEY,
        )
        if any(values) and not all(values):
            raise ValueError(
                "LLM fallback requires model name, base URL and API key together."
            )
        return self

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
