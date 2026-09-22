import logging
import re
import time
import uuid

from myone_auth.core.logging import request_id_ctx

logger = logging.getLogger("myone_auth.access")

# A client may supply its own ID to correlate across services, but it ends up in
# logs and response headers, so only a tight, boring alphabet is accepted.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestIdMiddleware:
    """Pure ASGI middleware: tags each request with an ID, echoes it in the
    X-Request-ID response header, and writes one access-log line."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = next(
            (v.decode("latin-1") for k, v in scope["headers"] if k == b"x-request-id"),
            None,
        )
        request_id = (
            supplied
            if supplied and _VALID_REQUEST_ID.fullmatch(supplied)
            else uuid.uuid4().hex
        )
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        status = 500  # what the client gets if the app raises before responding

        async def send_with_request_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            # Path only, never the query string: /authorize and the callback will
            # carry `code` and `state` there, and logs outlive their usefulness.
            logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            request_id_ctx.reset(token)
