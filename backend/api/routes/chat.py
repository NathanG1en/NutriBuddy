# backend/api/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException
import uuid
import re

import json
from fastapi.responses import StreamingResponse

from backend.api.schemas.chat import ChatRequest, ChatResponse
from backend.dependencies import get_agent
from backend.agent.graph import NutritionAgent
from backend.api.security import get_current_user

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: NutritionAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user),
):
    """Send a message to the nutrition agent."""
    try:
        thread_id = request.thread_id or str(uuid.uuid4())

        result = await agent.arun(request.message, thread_id=thread_id)
        response_text = result.get("message", "")
        image_path = result.get("image_path")
        exportable = result.get("exportable")
        artifacts = result.get("artifacts")

        return ChatResponse(
            response=response_text,
            thread_id=thread_id,
            image_path=image_path,
            exportable=exportable,
            artifacts=artifacts,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    agent: NutritionAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user),
):
    """Stream token-by-token tokens and tool execution artifacts via Server-Sent Events (SSE)."""
    thread_id = request.thread_id or str(uuid.uuid4())

    async def event_generator():
        try:
            async for event_data in agent.astream_events(
                request.message, thread_id=thread_id
            ):
                event_name = event_data.get("event", "message")
                payload = json.dumps(event_data.get("data", {}))
                yield f"event: {event_name}\ndata: {payload}\n\n"
        except Exception as e:
            error_payload = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{thread_id}")
async def get_history(thread_id: str, agent: NutritionAgent = Depends(get_agent)):
    """Get conversation history for a thread."""
    messages = agent.get_history(thread_id)

    return {
        "thread_id": thread_id,
        "message_count": len(messages),
        "messages": [
            {
                "role": msg.__class__.__name__.lower().replace("message", ""),
                "content": getattr(msg, "content", str(msg))[:500],
            }
            for msg in messages
        ],
    }
