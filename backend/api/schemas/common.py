# backend/api/schemas/common.py
from pydantic import BaseModel


class ToolInfo(BaseModel):
    name: str
    description: str


class HealthResponse(BaseModel):
    status: str
    agent: str
    tools_count: int
    api_version: str