"""Request logging middleware that appends one row per run to a CSV file.

Gives a persistent, analysable record of every analysis — how long it took,
what severities came back, how many rows were rejected — which the transient
console log does not. Useful for spotting slow runs or a spike in rejections
after a change.
"""

import csv
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("agent.runlog")

COLUMNS = [
    "timestamp",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "client",
    "rows_submitted",
    "critical",
    "warning",
    "normal",
    "unknown",
    "errors",
    "thread_id",
]


class RunLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, log_path: Optional[str] = None) -> None:
        super().__init__(app)
        self.path = Path(log_path or os.environ.get("RUN_LOG_PATH") or "logs/runs.csv")
        # Appends happen from the request handling threads, so serialise them —
        # interleaved writes would corrupt rows.
        self._lock = threading.Lock()
        self._ensure_header()

    def _ensure_header(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists() or self.path.stat().st_size == 0:
                with self.path.open("w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(COLUMNS)
        except OSError as exc:
            logger.warning("Could not initialise run log at %s: %s", self.path, exc)

    def _append(self, row: dict) -> None:
        try:
            with self._lock, self.path.open("a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)
        except OSError as exc:
            # Logging must never take down a request.
            logger.warning("Could not write run log row: %s", exc)

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        started = time.perf_counter()

        # Row count is read from the request body, which for /analyze_labs has
        # already been buffered by the time the response is produced.
        rows_submitted = ""
        if request.url.path == "/analyze_labs":
            try:
                payload = json.loads(await request.body())
                rows_submitted = len(payload.get("labs", []))
            except Exception:
                rows_submitted = ""

        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": f"{duration_ms:.0f}",
            "client": request.client.host if request.client else "",
            "rows_submitted": rows_submitted,
            "critical": "",
            "warning": "",
            "normal": "",
            "unknown": "",
            "errors": "",
            "thread_id": "",
        }

        # For an analysis, buffer the response so the severity counts can be
        # recorded, then re-emit it unchanged.
        if request.url.path == "/analyze_labs" and response.status_code == 200:
            body = b"".join([chunk async for chunk in response.body_iterator])
            try:
                data = json.loads(body)
                summary = data.get("summary", {})
                row.update(
                    critical=summary.get("critical", ""),
                    warning=summary.get("warning", ""),
                    normal=summary.get("normal", ""),
                    unknown=summary.get("unknown", ""),
                    errors=len(data.get("errors", [])),
                    thread_id=data.get("thread_id", ""),
                )
            except (ValueError, AttributeError):
                pass
            response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        self._append(row)
        return response
