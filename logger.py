#!/usr/bin/env python3
"""OpenClaw Structured Logger - JSON logging with rotation for all OpenClaw scripts"""

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(os.path.expanduser("~/.openclaw/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log files
APP_LOG = LOG_DIR / "openclaw-app.log"
TRADE_LOG = LOG_DIR / "openclaw-trades.log"
ERROR_LOG = LOG_DIR / "openclaw-errors.log"

# Rotation: 100MB max per file, keep 7 days worth (7 backups)
MAX_BYTES = 100 * 1024 * 1024  # 100MB
BACKUP_COUNT = 7


class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
        }

        # Add extra context if provided
        if hasattr(record, "context") and record.context:
            log_entry["context"] = record.context

        # Add exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(name, include_trade=False):
    """Get a configured JSON logger.

    Args:
        name: Logger name (e.g., 'trader', 'newsfeed', 'sentiment')
        include_trade: If True, also log to the dedicated trade log
    """
    logger = logging.getLogger(f"openclaw.{name}")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = JSONFormatter()

    # Main app log (all levels)
    app_handler = logging.handlers.RotatingFileHandler(
        APP_LOG, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(formatter)
    logger.addHandler(app_handler)

    # Error log (WARNING and above)
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # Trade log (if requested)
    if include_trade:
        trade_handler = logging.handlers.RotatingFileHandler(
            TRADE_LOG, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
        )
        trade_handler.setLevel(logging.INFO)
        trade_handler.setFormatter(formatter)
        logger.addHandler(trade_handler)

    return logger


def log_trade(logger, action, symbol, side, qty, price, **kwargs):
    """Convenience function for structured trade logging."""
    context = {
        "type": "trade",
        "action": action,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "value": round(qty * price, 2),
    }
    context.update(kwargs)
    logger.info(
        f"TRADE {action}: {side.upper()} {qty} x {symbol} @ ${price:.2f}",
        extra={"context": context},
    )


def log_api_call(logger, service, endpoint, status_code=None, error=None):
    """Log an API call for cost tracking."""
    context = {
        "type": "api_call",
        "service": service,
        "endpoint": endpoint,
    }
    if status_code:
        context["status_code"] = status_code
    if error:
        context["error"] = str(error)
        logger.warning(f"API {service} {endpoint}: error {error}", extra={"context": context})
    else:
        logger.info(f"API {service} {endpoint}: {status_code}", extra={"context": context})


# Quick test
if __name__ == "__main__":
    logger = get_logger("test", include_trade=True)
    logger.info("Logger initialized", extra={"context": {"source": "test"}})
    log_trade(logger, "proposal", "TSLA", "buy", 1, 250.00, reasoning="test trade")
    log_api_call(logger, "alpaca", "/v2/account", status_code=200)
    log_api_call(logger, "alpha_vantage", "/query", error="rate limit")

    print(f"App log:   {APP_LOG}")
    print(f"Trade log: {TRADE_LOG}")
    print(f"Error log: {ERROR_LOG}")
    print("\nTest entries written. Check with: jq . ~/.openclaw/logs/openclaw-app.log")
