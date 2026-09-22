import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Set by RequestIdMiddleware for the lifetime of one request. A ContextVar (not a
# global) so concurrent requests each see their own value.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has. Anything else came in through `extra=` and is
# copied into the JSON output.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "color_message",  # uvicorn's ANSI-coloured duplicate of the message
}


class RequestIdFilter(logging.Filter):
    """Stamps every record with the current request's ID (null outside a request)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line. json.dumps escapes newlines, so user-controlled
    text in a message cannot forge a second log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # uvicorn installs its own plain-text handlers; route it through ours instead.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # Silenced: RequestIdMiddleware writes its own access line, which carries the
    # request ID and (deliberately) leaves out the query string.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
