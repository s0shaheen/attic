"""Structured logging with correlation IDs for Lambda functions."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from typing import Any


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured Lambda logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "function": getattr(record, "function", "unknown"),
            "request_id": getattr(record, "request_id", "unknown"),
            "upload_id": getattr(record, "upload_id", "unknown"),
            "environment": os.environ.get("ENVIRONMENT", "dev"),
        }

        # Add duration if present
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Add error info if present
        if record.exc_info:
            log_entry["error"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


_loggers: dict[str, logging.Logger] = {}


def get_logger(function_name: str, correlation_id: str | None = None) -> logging.Logger:
    """Get a structured logger for a Lambda function.

    Creates a logger with JSON formatting and correlation ID support.
    Loggers are cached to avoid duplicate handlers.

    Args:
        function_name: Name of the Lambda function (used for filtering).
        correlation_id: Optional correlation ID for request tracing.

    Returns:
        Configured Logger instance.
    """
    if function_name in _loggers:
        return _loggers[function_name]

    logger = logging.getLogger(function_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    # Store default correlation ID
    logger.correlation_id = correlation_id or str(uuid.uuid4())  # type: ignore[attr-defined]

    _loggers[function_name] = logger
    return logger
