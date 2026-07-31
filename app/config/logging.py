import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger("app")
    root.setLevel(level.upper())
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.addHandler(handler)
    uvicorn_access.propagate = False
