"""MCP client used by the agent. Spawns mcp_server.py as a subprocess (stdio
transport) once at FastAPI startup and keeps one session open for the app's
lifetime — every agent tool call goes through this client.
"""

import contextlib
import json
import os
import sys
from typing import Any, Dict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MCPToolClient:
    def __init__(self) -> None:
        self._stack = contextlib.AsyncExitStack()
        self.session: Optional[ClientSession] = None

    async def start(self) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            cwd=BACKEND_DIR,
            env=os.environ.copy(),
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    async def stop(self) -> None:
        await self._stack.aclose()
        self.session = None

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if self.session is None:
            raise RuntimeError("MCP client not started")

        result = await self.session.call_tool(name, arguments)

        if result.isError:
            text = "".join(
                getattr(block, "text", "") for block in result.content if getattr(block, "type", None) == "text"
            )
            raise RuntimeError(f"MCP tool '{name}' failed: {text or 'unknown error'}")

        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured

        for block in result.content:
            if getattr(block, "type", None) == "text":
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return {"text": block.text}
        return {}
