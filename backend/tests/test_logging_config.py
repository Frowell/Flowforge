"""Tests for structured logging configuration.

Run with: pytest tests/test_logging_config.py -v --noconftest
"""

import io
import logging

import structlog


def test_configure_logging_runs_without_error():
    from app.core.logging_config import configure_logging

    configure_logging()


def test_stdlib_logger_works_after_configuration():
    from app.core.logging_config import configure_logging

    configure_logging()
    logger = logging.getLogger("test.stdlib")
    # Should not raise
    logger.info("test message from stdlib")


def test_structlog_contextvars_propagate():
    from app.core.logging_config import configure_logging

    configure_logging()

    # Capture log output
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
            ],
        )
    )

    test_logger = logging.getLogger("test.contextvars")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="test-123")

    test_logger.info("hello with context")

    output = stream.getvalue()
    assert "request_id" in output
    assert "test-123" in output

    structlog.contextvars.clear_contextvars()
