"""
Logging estructurado JSON (SP-6.4).
- Formatter que serializa cada registro como JSON con timestamp, level,
  logger, message y campos extra (request_id via contextvars).
- setup_logging() configura los loggers de la app.
"""

import json
import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key in ("route", "latency_ms", "status_code", "method"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.StreamHandler)]
    root.addHandler(handler)
    root.setLevel(level)
    # Reducir ruido de librerias
    for noisy in ("yfinance", "urllib3", "matplotlib", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)