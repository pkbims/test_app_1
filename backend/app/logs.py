"""Structured JSON logging: one object per line (PRD §17).

Every log line from the API and the worker is a single JSON object. The request
id flows from the client (`X-Request-Id`) through the API, onto the job row, and
into the worker's log lines, so one render is greppable end to end.

**Never logged:** photos or photo URLs, tokens, email addresses, prompt text —
people describe their homes in that text and it does not belong in a log file.
"""

from __future__ import annotations

import datetime as dt
import json
import logging

_RESERVED = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": dt.datetime.fromtimestamp(record.created, dt.UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(level: str = "info") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn's error/startup logs should flow through our JSON handler on root.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    # ...but its access log is redundant — RequestMiddleware writes the one line.
    access = logging.getLogger("uvicorn.access")
    access.handlers[:] = []
    access.propagate = False
    access.disabled = True
    # httpx logs its own "HTTP Request: GET https://...?...&api_key=..." line at
    # INFO — every query-string secret we ever send (SearchApi's api_key; the
    # worker also hands httpx our own short-lived signed render URLs) would
    # otherwise land in the log verbatim regardless of what our own code logs.
    # ORCH-QUESTIONS Q11 finding 2: this was a real leak, in production logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
