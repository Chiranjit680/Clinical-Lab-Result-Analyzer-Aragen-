"""Public entrypoint for lab analysis, backed by the LangGraph pipeline in graph.py.

Kept as a thin wrapper so routers/labs.py and main.py don't need to change:
they still call `analyze_labs(client, raw_labs)` — internally this now builds
(and caches) a compiled StateGraph closed over that client, and runs it.
"""

from typing import Any, Dict, List

from app.graph import build_graph
from app.mcp_client import MCPToolClient

_graph_cache: Dict[int, Any] = {}


def _get_graph(client: MCPToolClient):
    key = id(client)
    if key not in _graph_cache:
        _graph_cache[key] = build_graph(client)
    return _graph_cache[key]


async def analyze_labs(client: MCPToolClient, raw_labs: List[Dict[str, Any]]) -> Dict[str, Any]:
    graph = _get_graph(client)
    final_state = await graph.ainvoke({"raw_labs": raw_labs})
    return final_state["response"]
