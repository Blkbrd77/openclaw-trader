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


def test_get_logger(tmp_path, monkeypatch):
    import logger as logger_module

    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "APP_LOG", tmp_path / "app.log")
    monkeypatch.setattr(logger_module, "ERROR_LOG", tmp_path / "error.log")
    monkeypatch.setattr(logger_module, "TRADE_LOG", tmp_path / "trade.log")

    logger = logger_module.get_logger("unit_test")
    try:
        assert logger is not None
        assert logger.name == "openclaw.unit_test"
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
