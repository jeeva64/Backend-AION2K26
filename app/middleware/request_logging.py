import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("app.access")


class RequestLoggingMiddleware:
    """Structured JSON access log with a per-request id echoed back as X-Request-ID."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        request_id = uuid.uuid4().hex
        status_code = None

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status")
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode("ascii")))
            await send(message)

        await self.app(scope, receive, send_wrapper)

        headers = dict(scope.get("headers") or [])
        client = scope.get("client")
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "query_string": scope.get("query_string", b"").decode("latin-1"),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client[0] if client else None,
                    "user_agent": headers.get(b"user-agent", b"").decode("latin-1"),
                },
                ensure_ascii=False,
            )
        )
