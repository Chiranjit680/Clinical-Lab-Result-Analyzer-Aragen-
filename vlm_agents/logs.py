"""Logging for the agent pipeline.

Every record is tagged with the agent that emitted it (global, tile r1c2,
aggregator, model, mcp), because the tile agents run on parallel threads and
their steps interleave in the output.
"""
import contextlib
import contextvars
import logging
import sys
import time

FORMAT = "%(asctime)s %(levelname)-5s %(run)-8s %(agent)-12s %(message)s"
ROOT = "vlm_agents"

_run_id = contextvars.ContextVar("run_id", default="-")

# LangGraph fans the tile agents out across worker threads, and a context
# variable set on the request thread does not reach them. This mirror is read
# when that happens. It is a single value, so two runs genuinely in flight at
# once would share a label — acceptable here because provider rate limits mean
# the service handles roughly one image at a time.
_run_mirror = "-"


class _Context(logging.Filter):
    """Tags every record with its agent and the run it belongs to."""

    def filter(self, record):
        if not hasattr(record, "agent"):
            record.agent = record.name.rsplit(".", 1)[-1]
        from_context = _run_id.get()
        record.run = from_context if from_context != "-" else _run_mirror
        return True


@contextlib.contextmanager
def run_context(run_id: str):
    """Label every record emitted during one agent run, threads included."""
    global _run_mirror
    token = _run_id.set(run_id)
    previous_mirror, _run_mirror = _run_mirror, run_id
    try:
        yield
    finally:
        _run_id.reset(token)
        _run_mirror = previous_mirror


def setup(level="INFO", logfile=None):
    root = logging.getLogger(ROOT)
    root.setLevel(level.upper() if isinstance(level, str) else level)
    root.handlers.clear()
    root.propagate = False

    handlers = [logging.StreamHandler(sys.stderr)]
    if logfile:
        handlers.append(logging.FileHandler(logfile, mode="w"))
    for h in handlers:
        h.setFormatter(logging.Formatter(FORMAT, datefmt="%H:%M:%S"))
        h.addFilter(_Context())
        root.addHandler(h)
    return root


def get(agent: str):
    """A logger whose records carry `agent` as their label."""
    return logging.LoggerAdapter(logging.getLogger(ROOT), {"agent": agent})


def short(text, limit=160):
    """One-line preview of a model reply, for INFO-level logs."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


@contextlib.contextmanager
def timed(log, what, level=logging.INFO):
    """Log the start and the elapsed time of a step."""
    log.log(level, "%s ...", what)
    t0 = time.perf_counter()
    try:
        yield
    except Exception as e:
        log.error("%s FAILED after %.1fs: %s", what, time.perf_counter() - t0, e)
        raise
    else:
        log.log(level, "%s done in %.1fs", what, time.perf_counter() - t0)
