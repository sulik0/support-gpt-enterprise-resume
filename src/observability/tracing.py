import os
import logging
from typing import Any, Dict
from src.config import settings

logger = logging.getLogger("supportgpt.observability.tracing")


def get_tracer(name: str = "supportgpt"):
    from opentelemetry import trace

    return trace.get_tracer(name)


def set_span_attributes(span: Any, attributes: Dict[str, Any]) -> None:
    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            span.set_attribute(key, value)
        else:
            span.set_attribute(key, str(value))

def init_tracing() -> None:
    """Initialize OpenTelemetry and LangChain LangSmith tracing settings."""
    # LangSmith config
    langsmith_enabled = settings.LANGSMITH_TRACING or settings.LANGCHAIN_TRACING_V2
    if settings.LANGSMITH_TRACING:
        langsmith_api_key = settings.LANGSMITH_API_KEY or settings.LANGCHAIN_API_KEY
        langsmith_project = settings.LANGSMITH_PROJECT
    else:
        langsmith_api_key = settings.LANGCHAIN_API_KEY or settings.LANGSMITH_API_KEY
        langsmith_project = settings.LANGCHAIN_PROJECT

    if langsmith_enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
            os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = langsmith_project
        os.environ["LANGCHAIN_PROJECT"] = langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        if settings.LANGSMITH_WORKSPACE_ID:
            os.environ["LANGSMITH_WORKSPACE_ID"] = settings.LANGSMITH_WORKSPACE_ID
        logger.info("LangSmith tracing enabled and environment variables configured.")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("LangSmith tracing is disabled.")

    # OpenTelemetry config (simulated hook or basic setup)
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        provider = TracerProvider()
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry TracerProvider initialized with Console Exporter.")
    except Exception as e:
        logger.warning(f"Could not initialize OpenTelemetry exporter: {e}")
