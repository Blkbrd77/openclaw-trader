"""Tests for OpenClaw structured logger."""

import json


def test_json_formatter():
    from logger import JSONFormatter
    import logging

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="openclaw.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["source"] == "openclaw.test"
    assert data["message"] == "Test message"
    assert "timestamp" in data


def test_json_formatter_with_context():
    from logger import JSONFormatter
    import logging

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="openclaw.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test",
        args=(),
        exc_info=None,
    )
    record.context = {"type": "trade", "symbol": "TSLA"}
    output = formatter.format(record)
    data = json.loads(output)
    assert data["context"]["type"] == "trade"
    assert data["context"]["symbol"] == "TSLA"


def test_get_logger():
    from logger import get_logger
    logger = get_logger("unit_test")
    assert logger is not None
    assert logger.name == "openclaw.unit_test"
