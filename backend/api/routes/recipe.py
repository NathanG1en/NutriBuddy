# backend/api/routes/recipe.py
from fastapi import APIRouter, Depends
from pathlib import Path
from datetime import datetime

from backend.api.schemas.recipe import (
    RecipeRequest,
    RecipeNutrition,
    LabelRequest,
    Ingredient,
    ParseRecipeRequest,
    ParseRecipeResponse,
    ParsedIngredientResponse,
)
from backend.dependencies import get_nutrition_service, get_label_service
from backend.services.nutrition import NutritionService
from backend.services.labels import LabelService, LabelLayoutConfig
from backend.services.ingredient_parser import IngredientParser
from backend.services.unit_converter import UnitConverter

router = APIRouter()


@router.post("/calculate", response_model=RecipeNutrition)
async def calculate_recipe(
    request: RecipeRequest,
    nutrition_service: NutritionService = Depends(get_nutrition_service),
):
    """Calculate nutrition for a recipe (live preview) with natural unit conversion."""
    ingredients = [i.model_dump() for i in request.ingredients]
    result = await nutrition_service.calculate_recipe_async(ingredients)

    # Calculate total grams from resolved ingredients
    total_grams = sum(i.get("grams", 0.0) for i in result["ingredients"] if "error" not in i)
    scale = request.serving_size_grams / total_grams if total_grams > 0 else 1

    per_serving = {
        key: round(value * scale, 2) for key, value in result["recipe_totals"].items()
    }

    return RecipeNutrition(
        recipe_name=request.recipe_name,
        serving_size=f"{request.serving_size_grams}g",
        servings=request.servings_per_container,
        totals=result["recipe_totals"],
        per_serving=per_serving,
        ingredients=result["ingredients"],
    )


@router.post("/parse", response_model=ParseRecipeResponse)
async def parse_recipe(request: ParseRecipeRequest):
    """Parse raw multi-line recipe text into structured ingredients with estimated gram weights."""
    parsed_items = await IngredientParser.parse_with_llm_fallback(request.recipe_text)
    response_items = []

    for item in parsed_items:
        conv = UnitConverter.resolve_to_grams(
            quantity=item.quantity,
            unit=item.unit,
            food_name=item.food_name,
        )
        response_items.append(
            ParsedIngredientResponse(
                raw_text=item.raw_text,
                food_name=item.food_name,
                quantity=item.quantity,
                unit=item.unit,
                preparation=item.preparation,
                confidence=item.confidence,
                estimated_grams=conv.get("grams"),
            )
        )

    return ParseRecipeResponse(ingredients=response_items)


@router.post("/label")
async def generate_label(
    request: LabelRequest, label_service: LabelService = Depends(get_label_service)
):
    """Generate a nutrition label image."""
    layout = LabelLayoutConfig(
        serving_size=request.serving_size,
        servings_per_container=request.servings,
    )

    service = LabelService(layout=layout)
    image_bytes = service.generate_image(request.nutrition, request.recipe_name)

    # Save image
    labels_dir = Path(__file__).parent.parent.parent / "data" / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in request.recipe_name)[:30]
    filename = f"{safe_name}_{timestamp}.png"

    (labels_dir / filename).write_bytes(image_bytes)

    return {"filename": filename, "url": f"/labels/{filename}"}


@router.get("/search")
async def search_food(
    query: str, nutrition_service: NutritionService = Depends(get_nutrition_service)
):
    """Search for a food (autocomplete)."""
    result = await nutrition_service.search_async(query)
    if result:
        return {"fdc_id": result.get("fdcId"), "description": result.get("description")}
    return {"error": "Not found"}
