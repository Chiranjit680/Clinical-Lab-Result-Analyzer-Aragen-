import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent import ask_followup

logger = logging.getLogger("agent")

router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat/{thread_id}")
async def chat_socket(websocket: WebSocket, thread_id: str) -> None:
    """Follow-up chat over a parked analysis thread.

    Protocol (JSON both ways):
      client -> {"question": "..."}
      server -> {"type": "answer"|"error"|"status", "content": "..."}
    """
    await websocket.accept()
    logger.info("[%s] chat socket opened", thread_id)

    try:
        await websocket.send_json(
            {"type": "status", "content": "Connected — ask anything about these results."}
        )
        while True:
            payload = await websocket.receive_json()
            question = str(payload.get("question", "")).strip()
            if not question:
                await websocket.send_json({"type": "error", "content": "Empty question."})
                continue

            try:
                answer = await ask_followup(websocket.app.state.mcp_client, thread_id, question)
            except Exception as exc:
                logger.exception("[%s] chat failed", thread_id)
                await websocket.send_json({"type": "error", "content": f"Chat failed: {exc}"})
                continue

            if answer is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": (
                            "This analysis session is no longer available "
                            "(the server may have restarted). Re-run the analysis to chat about it."
                        ),
                    }
                )
                continue

            await websocket.send_json({"type": "answer", "content": answer})
    except WebSocketDisconnect:
        logger.info("[%s] chat socket closed", thread_id)
