from typing import Any


class SecurityHeadersMiddleware:
    """Inject security-related HTTP headers into every response."""

    _HEADERS = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cross-Origin-Opener-Policy": "same-origin",
    }

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].extend(
                    (key.encode("latin-1"), value.encode("latin-1"))
                    for key, value in self._HEADERS.items()
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
