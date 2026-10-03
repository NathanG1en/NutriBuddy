# backend/api/schemas/recipe.py
from pydantic import BaseModel
from typing import Optional


class Ingredient(BaseModel):
    name: str
    grams: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    raw_text: Optional[str] = None
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


class ParseRecipeRequest(BaseModel):
    recipe_text: str


class ParsedIngredientResponse(BaseModel):
    raw_text: str
    food_name: str
    quantity: float
    unit: Optional[str] = None
    preparation: Optional[str] = None
    confidence: float
    estimated_grams: Optional[float] = None


class ParseRecipeResponse(BaseModel):
    ingredients: list[ParsedIngredientResponse]