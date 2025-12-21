# backend/api/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException
import uuid
import re

from backend.api.schemas.chat import ChatRequest, ChatResponse
from backend.dependencies import get_agent
from backend.agent.graph import NutritionAgent

router = APIRouter()


def extract_image_path(text: str) -> str | None:
    """Extract image filename from agent response."""
    match = re.search(r"/labels/([A-Za-z0-9_]+\.png)", text)
    if match:
        return f"http://localhost:8000/labels/{match.group(1)}"
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(
        request: ChatRequest,
        agent: NutritionAgent = Depends(get_agent)
):
    """Send a message to the nutrition agent."""
    try:
        thread_id = request.thread_id or str(uuid.uuid4())

        result = agent.run(request.message, thread_id=thread_id)
        response_text = result.get("message", "")
        image_path = extract_image_path(response_text)

        return ChatResponse(
            response=response_text,
            thread_id=thread_id,
            image_path=image_path
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{thread_id}")
async def get_history(
        thread_id: str,
        agent: NutritionAgent = Depends(get_agent)
):
    """Get conversation history for a thread."""
    messages = agent.get_history(thread_id)

    return {
        "thread_id": thread_id,
        "message_count": len(messages),
        "messages": [
            {
                "role": msg.__class__.__name__.lower().replace("message", ""),
                "content": getattr(msg, "content", str(msg))[:500]
            }
            for msg in messages
        ]
    }