# backend/api/schemas/recipe.py
from pydantic import BaseModel
from typing import Optional


class Ingredient(BaseModel):
    name: str
    grams: float
    fdc_id: Optional[int] = None


class RecipeRequest(BaseModel):
    recipe_name: str
    ingredients: list[Ingredient]
    serving_size_grams: float = 100
    servings_per_container: int = 1


class RecipeNutrition(BaseModel):
    recipe_name: str
    serving_size: str
    servings: int
    totals: dict
    per_serving: dict
    ingredients: list[dict]


class LabelRequest(BaseModel):
    recipe_name: str
    nutrition: dict
    serving_size: str = "100g"
    servings: int = 1