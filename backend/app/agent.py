"""Public entrypoint for lab analysis, backed by the LangGraph pipeline in graph.py.

Kept as a thin wrapper so routers/labs.py and main.py don't need to change:
they still call `analyze_labs(client, raw_labs)` — internally this now builds
(and caches) a compiled StateGraph closed over that client, and runs it.
"""

import logging
import time
import uuid
from typing import Any, Dict, List

from app.graph import build_graph
from app.mcp_client import MCPToolClient

logger = logging.getLogger("agent")

_graph_cache: Dict[int, Any] = {}


def _get_graph(client: MCPToolClient):
    key = id(client)
    if key not in _graph_cache:
        _graph_cache[key] = build_graph(client)
    return _graph_cache[key]


async def analyze_labs(client: MCPToolClient, raw_labs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Short id so every log line from one request can be traced together, even
    # when several analyses overlap.
    run_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()

    logger.info("[%s] ===== AGENT RUN START | %d row(s) =====", run_id, len(raw_labs))
    graph = _get_graph(client)
    try:
        final_state = await graph.ainvoke({"raw_labs": raw_labs, "run_id": run_id})
    except Exception:
        logger.exception("[%s] ===== AGENT RUN FAILED =====", run_id)
        raise

    elapsed = time.perf_counter() - started
    summary = final_state["response"]["summary"]
    logger.info("[%s] ===== AGENT RUN END | %s in %.2fs =====", run_id, summary, elapsed)
    return final_state["response"]
