"""SupportGPT 应用日志初始化。"""

import logging
from typing import TextIO


_HANDLER_MARKER = "_supportgpt_console_handler"
_STRUCTURED_FIELDS = (
    "request_id",
    "trace_id",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "ticket_id",
    "intent",
    "priority",
    "citations",
    "tool",
    "tool_count",
    "generated",
    "score",
    "hallucination_detected",
    "required",
    "risk_level",
    "risk_score",
    "security_source",
    "error_type",
)


class RequestContextFilter(logging.Filter):
    """为业务日志补充当前请求与 Trace 关联字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from src.observability.tracing import get_current_trace_id, get_request_id

            if not getattr(record, "request_id", None):
                record.request_id = get_request_id()
            if not getattr(record, "trace_id", None):
                record.trace_id = get_current_trace_id()
        except Exception:
            record.request_id = getattr(record, "request_id", None)
            record.trace_id = getattr(record, "trace_id", None)
        return True


class StructuredTextFormatter(logging.Formatter):
    """以易读文本输出消息，并追加有限的结构化业务字段。"""

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        attributes = []
        for field_name in _STRUCTURED_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None and value != "":
                attributes.append(f"{field_name}={value}")
        return f"{rendered} | {' '.join(attributes)}" if attributes else rendered


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """幂等初始化 SupportGPT Logger，确保 Uvicorn 下也输出业务 INFO 日志。"""
    normalized_level = getattr(logging, level.upper(), logging.INFO)
    application_logger = logging.getLogger("supportgpt")
    application_logger.setLevel(normalized_level)
    application_logger.propagate = False

    handler = next(
        (
            item
            for item in application_logger.handlers
            if getattr(item, _HANDLER_MARKER, False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(stream)
        setattr(handler, _HANDLER_MARKER, True)
        handler.addFilter(RequestContextFilter())
        handler.setFormatter(
            StructuredTextFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        application_logger.addHandler(handler)
    handler.setLevel(normalized_level)
