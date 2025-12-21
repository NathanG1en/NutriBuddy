# backend/api/schemas/chat.py
from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    image_path: Optional[str] = None
    exportable: Optional[dict] = None  # For recipe builder export