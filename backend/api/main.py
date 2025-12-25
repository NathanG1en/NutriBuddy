# backend/api/main.py
"""FastAPI app setup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.api.routes import chat, recipe, health, voice, rag


app = FastAPI(
    title="Nutrition Agent API",
    description="AI-powered nutrition label generation API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for labels
labels_dir = Path(__file__).parent.parent / "data" / "labels"
labels_dir.mkdir(parents=True, exist_ok=True)
app.mount("/labels", StaticFiles(directory=str(labels_dir)), name="labels")

# Mount routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(recipe.router, prefix="/api/recipe", tags=["Recipe"])
app.include_router(voice.router, prefix="/api", tags=["Voice"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)