from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
from firebase_admin import firestore

from backend.api.security import get_current_user, get_db
from backend.dependencies import get_agent

router = APIRouter()

# --- Models ---


class AnalyzeRecipeRequest(BaseModel):
    recipe_name: str
    ingredients: List[str]  # e.g. ["2 eggs", "1 cup flour"]


class LabelData(BaseModel):
    title: str
    image_url: str | None = None
    nutrition: Dict[str, Any]  # The raw nutrition data
    ingredients: List[str]
    created_at: datetime | None = None


class SavedLabel(LabelData):
    id: str


# --- Endpoints ---


@router.post("/analyze")
async def analyze_recipe(
    request: AnalyzeRecipeRequest,
    current_user: dict = Depends(get_current_user),
    agent=Depends(get_agent),
):
    """
    Uses the Nutrition Agent to analyze a recipe, calculate nutrition,
    and generate a label image.
    """
    try:
        # Construct the prompt
        prompt = (
            f"Analyze this recipe: '{request.recipe_name}'.\n"
            f"Ingredients: {', '.join(request.ingredients)}.\n"
            "1. Convert ingredients to grams.\n"
            "2. Calculate total nutrition.\n"
            "3. Generate a nutrition label image.\n"
            "IMPORTANT: At the end, output the finalized ingredients list as a JSON block:\n"
            "```json\n"
            '[{"name": "...", "grams": 100}, ...]\n'
            "```\n"
            "Return the final nutrition totals, the image URL, and the JSON block."
        )

        # Run agent
        result = agent.run(prompt, thread_id=f"user_{current_user['uid']}")
        response_text = result["message"]

        # Extract Image URL
        import re
        import json

        image_match = re.search(r"(/labels/[\w_]+\.png)", response_text)
        image_url = image_match.group(1) if image_match else None

        # Extract JSON Ingredients
        ingredients_match = re.search(r"```json(.*?)```", response_text, re.DOTALL)
        structured_ingredients = []
        if ingredients_match:
            try:
                structured_ingredients = json.loads(ingredients_match.group(1).strip())
            except:
                pass

        return {
            "analysis": response_text,
            "image_url": image_url,
            "ingredients": structured_ingredients,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=dict)
async def save_label(
    label: LabelData, current_user: dict = Depends(get_current_user), db=Depends(get_db)
):
    """Save a generated label."""
    try:
        user_id = current_user["uid"]
        data = label.model_dump()
        data["created_at"] = datetime.utcnow()
        data["user_id"] = user_id

        doc_ref = (
            db.collection("users").document(user_id).collection("labels").document()
        )
        doc_ref.set(data)

        return {"status": "success", "id": doc_ref.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[SavedLabel])
async def list_labels(
    current_user: dict = Depends(get_current_user), db=Depends(get_db)
):
    """List saved labels."""
    try:
        user_id = current_user["uid"]
        labels_ref = db.collection("users").document(user_id).collection("labels")
        docs = labels_ref.order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).stream()

        return [SavedLabel(id=doc.id, **doc.to_dict()) for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
