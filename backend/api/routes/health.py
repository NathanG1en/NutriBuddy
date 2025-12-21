# backend/api/routes/health.py
from fastapi import APIRouter, Depends

from backend.api.schemas.common import ToolInfo, HealthResponse
from backend.dependencies import get_agent
from backend.agent.graph import NutritionAgent

router = APIRouter()


@router.get("/")
async def root():
    return {"status": "healthy", "service": "Nutrition Agent API", "version": "1.0.0"}


@router.get("/api/health", response_model=HealthResponse)
async def health_check(agent: NutritionAgent = Depends(get_agent)):
    return HealthResponse(
        status="healthy",
        agent="ready",
        tools_count=len(agent.tools),
        api_version="1.0.0"
    )


@router.get("/api/tools")
async def get_tools(agent: NutritionAgent = Depends(get_agent)):
    return {
        "count": len(agent.tools),
        "tools": [
            ToolInfo(name=t.name, description=t.description or "")
            for t in agent.tools
        ]
    }