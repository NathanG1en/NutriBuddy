from fastapi import APIRouter, HTTPException, Depends, status
from firebase_admin import firestore
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from backend.api.security import get_current_user, get_db

router = APIRouter()


class Ingredient(BaseModel):
    item: str
    quantity: str
    unit: str
    notes: str = ""


class SaveRecipeRequest(BaseModel):
    title: str
    description: str
    ingredients: List[Ingredient]
    instructions: List[str]
    science_notes: str = ""


class SavedRecipe(SaveRecipeRequest):
    id: str
    created_at: datetime


@router.post("/", response_model=dict)
async def save_recipe(
    recipe: SaveRecipeRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Saves a recipe to the user's collection."""
    try:
        user_id = current_user["uid"]
        recipe_data = recipe.model_dump()
        recipe_data["created_at"] = datetime.utcnow()
        recipe_data["user_id"] = user_id

        # Add to subcollection: users/{uid}/recipes
        doc_ref = (
            db.collection("users").document(user_id).collection("recipes").document()
        )
        doc_ref.set(recipe_data)

        return {"status": "success", "id": doc_ref.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[SavedRecipe])
async def list_recipes(
    current_user: dict = Depends(get_current_user), db=Depends(get_db)
):
    """Lists saved recipes for the current user."""
    try:
        user_id = current_user["uid"]
        recipes_ref = db.collection("users").document(user_id).collection("recipes")
        docs = recipes_ref.order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append(SavedRecipe(id=doc.id, **data))

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{recipe_id}")
async def delete_recipe(
    recipe_id: str, current_user: dict = Depends(get_current_user), db=Depends(get_db)
):
    """Deletes a saved recipe."""
    try:
        user_id = current_user["uid"]
        doc_ref = (
            db.collection("users")
            .document(user_id)
            .collection("recipes")
            .document(recipe_id)
        )
        doc_ref.delete()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
