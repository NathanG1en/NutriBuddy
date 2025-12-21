"""
FastAPI backend for Nutrition Agent
Run with: uvicorn backend.api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uuid
import re

from backend.agent.graph import NutritionAgent


# ============================================
# FastAPI Setup
# ============================================

app = FastAPI(
    title="Nutrition Agent API",
    description="AI-powered nutrition label generation API",
    version="1.0.0"
)

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

# Mount static files for label images
labels_dir = Path(__file__).parent.parent / "data" / "labels"
labels_dir.mkdir(parents=True, exist_ok=True)
app.mount("/labels", StaticFiles(directory=str(labels_dir)), name="labels")

# Initialize agent
agent = NutritionAgent()


# ============================================
# Request/Response Models
# ============================================

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    image_path: Optional[str] = None


class ToolInfo(BaseModel):
    name: str
    description: str


# ============================================
# Helpers
# ============================================

def extract_image_path(text: str) -> Optional[str]:
    """Extract image filename from agent response and return full URL."""
    # Look for pattern like "Access at /labels/filename.png"
    match = re.search(r"/labels/([A-Za-z0-9_]+\.png)", text)
    if match:
        return f"http://localhost:8000/labels/{match.group(1)}"
    return None


# ============================================
# API Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Nutrition Agent API",
        "version": "1.0.0"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the nutrition agent."""
    try:
        thread_id = request.thread_id or str(uuid.uuid4())
        
        result = agent.run(request.message, thread_id=thread_id)
        response_text = result.get("message", "")
        
        # Try to extract image path from the response
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


@app.get("/api/history/{thread_id}")
async def get_history(thread_id: str):
    """Get conversation history for a thread."""
    messages = agent.get_history(thread_id)
    
    history = []
    for msg in messages:
        history.append({
            "role": msg.__class__.__name__.lower().replace("message", ""),
            "content": getattr(msg, "content", str(msg))[:500]
        })
    
    return {
        "thread_id": thread_id,
        "message_count": len(history),
        "messages": history
    }


@app.get("/api/tools")
async def get_tools():
    """Get list of available tools."""
    tools_info = [
        ToolInfo(name=t.name, description=t.description or "")
        for t in agent.tools
    ]
    
    return {
        "count": len(tools_info),
        "tools": tools_info
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "agent": "ready",
        "tools_count": len(agent.tools),
        "api_version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)

# ============================================
# Recipe Builder Models
# ============================================

class Ingredient(BaseModel):
    name: str
    grams: float
    fdc_id: Optional[int] = None  # If already resolved


class RecipeRequest(BaseModel):
    recipe_name: str
    ingredients: list[Ingredient]
    serving_size_grams: float = 100
    servings_per_container: int = 1


class RecipeNutrition(BaseModel):
    recipe_name: str
    serving_size: str
    servings: int
    totals: dict  # Full recipe totals
    per_serving: dict  # Scaled to serving size
    ingredients: list[dict]  # Per-ingredient breakdown


class LabelRequest(BaseModel):
    recipe_name: str
    nutrition: dict  # Can be per_serving from RecipeNutrition
    serving_size: str = "100g"
    servings: int = 1


# ============================================
# Recipe Builder Endpoints
# ============================================

@app.post("/api/recipe/calculate", response_model=RecipeNutrition)
async def calculate_recipe(request: RecipeRequest):
    """
    Calculate nutrition for a recipe. 
    Used by the manual recipe builder for live preview.
    """
    from backend.services.nutrition import NutritionService
    
    service = NutritionService()
    
    # Convert to format expected by service
    ingredients = [{"name": i.name, "grams": i.grams} for i in request.ingredients]
    result = service.calculate_recipe(ingredients)
    
    # Calculate per-serving values
    total_grams = sum(i.grams for i in request.ingredients)
    scale = request.serving_size_grams / total_grams if total_grams > 0 else 1
    
    per_serving = {}
    for key, value in result["recipe_totals"].items():
        per_serving[key] = round(value * scale, 2)
    
    return RecipeNutrition(
        recipe_name=request.recipe_name,
        serving_size=f"{request.serving_size_grams}g",
        servings=request.servings_per_container,
        totals=result["recipe_totals"],
        per_serving=per_serving,
        ingredients=result["ingredients"]
    )


@app.post("/api/recipe/label")
async def generate_recipe_label(request: LabelRequest):
    """
    Generate a nutrition label image for a recipe.
    Returns the image URL.
    """
    from backend.services.labels import LabelService, LabelLayoutConfig
    from pathlib import Path
    from datetime import datetime
    
    # Create label with custom serving info
    layout = LabelLayoutConfig(
        serving_size=request.serving_size,
        servings_per_container=request.servings,
    )
    
    service = LabelService(layout=layout)
    image_bytes = service.generate_image(request.nutrition, request.recipe_name)
    
    # Save image
    labels_dir = Path(__file__).parent.parent / "data" / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in request.recipe_name)[:30]
    filename = f"{safe_name}_{timestamp}.png"
    
    filepath = labels_dir / filename
    filepath.write_bytes(image_bytes)
    
    return {
        "filename": filename,
        "url": f"http://localhost:8000/labels/{filename}",
        "recipe_name": request.recipe_name
    }


@app.get("/api/food/search")
async def search_food(query: str):
    """
    Search for a food item. Used by recipe builder autocomplete.
    """
    from backend.services.nutrition import NutritionService
    
    service = NutritionService()
    result = service.search(query)
    
    if result:
        return {
            "fdc_id": result.get("fdcId"),
            "description": result.get("description"),
            "brand": result.get("brandOwner", "Generic")
        }
    return {"error": "No results found"}