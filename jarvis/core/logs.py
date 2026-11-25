"""JSON logs that hold ids, timings and counts only, never what he said or anything secret (C21).

Every line is one JSON object: `{ts, level, logger, event, ...fields}`.
- `event` is a code-made name (`job.done`, `http.request`); a message that isn't one (free text from a library,
  an f-string) is dropped and logged as `unnamed`.
- A field is kept only if its name says it is an id, a timing, a count or a fixed code (see `KEEP`), its name has
  nothing secret-sounding in it (`SECRET`), and its value is a number, a bool or a short token with no spaces.
- Exceptions are logged as their class name only: no message, no traceback (they can carry text or keys).

Use `EventLog("jarvis.core.queue").info("job.done", job_id=..., ms=...)`.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import re
import sys
import time
from pathlib import Path

EVENT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
KEEP = re.compile(r"^(id|[a-z0-9_]+_id|ids|ms|[a-z0-9_]+_ms|n|[a-z0-9_]+_n|count|[a-z0-9_]+_count|attempt|attempts|"
                  r"status|state|code|error|component|kind|route|method|level|port|pid|version|reason|tier|v|"
                  r"turn|tool|stage|stop|device|mb|[a-z0-9_]+_mb|pct|[a-z0-9_]+_pct)$")
SECRET = re.compile(r"(key|token|secret|passw|auth|cookie|credential|bearer)", re.IGNORECASE)
TOKEN = re.compile(r"^[A-Za-z0-9/][A-Za-z0-9._:/{}+-]{0,79}$")  # a short code-like value: no spaces, so no sentences
HANDLER_NAME = "jarvis-core-json"
STANDARD = frozenset(logging.LogRecord("x", 0, "x", 0, "", None, None).__dict__) | {"message", "asctime", "taskName"}


def clean(fields: dict) -> dict:
    """Only what C21 allows. T0 (pure, microseconds)."""
    out: dict = {}
    for key, value in fields.items():
        if not isinstance(key, str) or not KEEP.match(key) or SECRET.search(key):
            continue
        if isinstance(value, bool) or value is None:
            out[key] = value
        elif isinstance(value, int | float):
            out[key] = round(value, 2) if isinstance(value, float) else value
        elif isinstance(value, str) and TOKEN.match(value) and not SECRET.search(value):
            out[key] = value
        elif isinstance(value, list | tuple) and key == "ids":
            out[key] = [v for v in value if isinstance(v, str) and TOKEN.match(v)][:50]
    return out


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.msg if isinstance(record.msg, str) and not record.args else None
        event = message if message and EVENT.match(message) else "unnamed"
        line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)) + f".{int(record.msecs):03d}",
                "level": record.levelname.lower(), "logger": record.name if EVENT.match(record.name) else "other",
                "event": event}
        # fields given the plain logging way (extra={"turn": ...}) count too (v0.14.0): the voice loop's warnings
        # used to arrive here with nothing but their name, so "tool.failed" never said which tool or why
        plain = {k: v for k, v in record.__dict__.items() if k not in STANDARD and k != "jv"}
        line.update(clean(plain))
        line.update(clean(getattr(record, "jv", {}) or {}))
        if record.exc_info and record.exc_info[0] is not None:
            line["error"] = record.exc_info[0].__name__  # the class name only
        return json.dumps(line, separators=(",", ":"))


def setup_logging(log_file: Path | None, level: int = logging.INFO, stream: bool = True) -> None:
    """Send every log line (ours, uvicorn's, libraries') through the JSON formatter. Replaces the handlers a previous
    call installed, so tests and restarts don't double up. T1 (once at start)."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == HANDLER_NAME]:
        root.removeHandler(handler)
        handler.close()
    handlers: list[logging.Handler] = []
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"))
    if stream:
        handlers.append(logging.StreamHandler(sys.stderr))
    for handler in handlers:
        handler.set_name(HANDLER_NAME)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):  # no handlers of their own: everything goes through ours
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True  # client addresses and raw paths; we log our own request line


class EventLog:
    """A logger that takes an event name and allowed fields only."""

    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def _emit(self, level: int, event: str, exc: bool = False, **fields) -> None:
        if self._log.isEnabledFor(level):
            self._log.log(level, event, extra={"jv": fields}, exc_info=exc)

    def debug(self, event: str, **fields) -> None: self._emit(logging.DEBUG, event, **fields)
    def info(self, event: str, **fields) -> None: self._emit(logging.INFO, event, **fields)
    def warning(self, event: str, **fields) -> None: self._emit(logging.WARNING, event, **fields)
    def error(self, event: str, **fields) -> None: self._emit(logging.ERROR, event, **fields)

    def exception(self, event: str, **fields) -> None:
        """Inside an `except`: logs the exception's class name, never its message."""
        self._emit(logging.ERROR, event, exc=True, **fields)
