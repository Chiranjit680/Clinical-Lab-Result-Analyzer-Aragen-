"""Public entrypoint for lab analysis, backed by the LangGraph pipeline in graph.py.

The compiled graph is checkpointed, so a run pauses at the `chat` node once the
analysis is aggregated. `/analyze_labs` returns the results plus the thread_id;
the WebSocket in routers/chat.py then resumes that same thread per question,
which keeps the full analysis in context without re-sending it.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph import build_graph
from app.mcp_client import MCPToolClient

logger = logging.getLogger("agent")

# In-process checkpointer: threads live for the lifetime of the server only.
# Swap for SqliteSaver/PostgresSaver to survive restarts or run multiple workers.
_checkpointer = MemorySaver()
_graph_cache: Dict[int, Any] = {}

# A chat thread parks at the interrupt indefinitely; each answered question is
# one super-step, so the default limit of 25 would cut the conversation short.
RECURSION_LIMIT = 500


def _get_graph(client: MCPToolClient):
    key = id(client)
    if key not in _graph_cache:
        _graph_cache[key] = build_graph(client, checkpointer=_checkpointer)
    return _graph_cache[key]


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


async def analyze_labs(client: MCPToolClient, raw_labs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Doubles as the checkpoint thread_id, so log lines and the chat session
    # for one analysis share an identifier.
    run_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()

    logger.info("[%s] ===== AGENT RUN START | %d row(s) =====", run_id, len(raw_labs))
    graph = _get_graph(client)
    try:
        state = await graph.ainvoke({"raw_labs": raw_labs, "run_id": run_id}, _config(run_id))
    except Exception:
        logger.exception("[%s] ===== AGENT RUN FAILED =====", run_id)
        raise

    elapsed = time.perf_counter() - started
    response = dict(state["response"])
    response["thread_id"] = run_id

    logger.info(
        "[%s] ===== AGENT RUN END | %s in %.2fs | thread parked for chat =====",
        run_id,
        response["summary"],
        elapsed,
    )
    return response


async def ask_followup(client: MCPToolClient, thread_id: str, question: str) -> Optional[str]:
    """Resume a parked analysis thread with a follow-up question.

    Returns the assistant's answer, or None if the thread is unknown (e.g. the
    server restarted, since MemorySaver holds state in process memory only).
    """
    graph = _get_graph(client)
    config = _config(thread_id)

    snapshot = await graph.aget_state(config)
    if not snapshot or not snapshot.values:
        logger.warning("[%s] chat requested for unknown/expired thread", thread_id)
        return None

    state = await graph.ainvoke(Command(resume=question), config)
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "assistant":
            return message.get("content", "")
    return None
