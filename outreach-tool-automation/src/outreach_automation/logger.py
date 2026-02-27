from __future__ import annotations

import logging
from typing import Any

_REDACT_KEYS = {
    "token",
    "refresh_token",
    "authorization",
    "cookie",
    "session_data",
    "password",
    "secret",
}


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.args, dict):
            record.args = {k: self._redact(k, v) for k, v in record.args.items()}
        return super().format(record)

    def _redact(self, key: str, value: Any) -> Any:
        lowered = key.lower()
        if any(s in lowered for s in _REDACT_KEYS):
            return "***REDACTED***"
        return value


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
