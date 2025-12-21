# backend/agent/tools.py
"""LangChain tools - thin wrappers around services."""

import json
from datetime import datetime
from langchain_core.tools import tool
from backend.services.nutrition import NutritionService
from backend.services.labels import LabelService

# Lazy init
_nutrition_service: NutritionService | None = None
_label_service: LabelService | None = None


def _get_nutrition_service() -> NutritionService:
    global _nutrition_service
    if _nutrition_service is None:
        _nutrition_service = NutritionService()
    return _nutrition_service


def _get_label_service() -> LabelService:
    global _label_service
    if _label_service is None:
        _label_service = LabelService()
    return _label_service


# ============================================
# Nutrition Tools
# ============================================

@tool
def search_foods(query: str) -> str:
    """
    Search for a food in the USDA database.
    
    Args:
        query: Food name to search for (e.g., "avocado", "chicken breast")
    
    Returns:
        JSON with the best matching food and its FDC ID
    """
    result = _get_nutrition_service().search(query)
    if result:
        return json.dumps({
            "fdc_id": result.get("fdcId"),
            "description": result.get("description"),
            "brand": result.get("brandOwner", "Generic")
        }, indent=2)
    return json.dumps({"error": "No results found"})


@tool
def get_nutrition(fdc_id: str) -> str:
    """
    Get nutrition data for a food by its FDC ID.
    
    Args:
        fdc_id: The FDC ID from search results
    
    Returns:
        JSON with nutrition facts (calories, protein, carbs, fat, etc.)
    """
    result = _get_nutrition_service().get_nutrition(int(fdc_id))
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({"error": "Food not found"})


@tool
def calculate_recipe_nutrition(ingredients_json: str) -> str:
    """
    Calculate combined nutrition for a recipe with multiple ingredients.
    
    Args:
        ingredients_json: JSON array of ingredients, e.g.:
            [{"name": "eggs", "quantity": 2}, {"name": "flour", "quantity": 1}]
        recipe_name: Name of the recipe
    
    Returns:
        JSON with total nutrition and per-ingredient breakdown
    """
    try:
        ingredients = json.loads(ingredients_json)
        result = _get_nutrition_service().calculate_recipe(ingredients)
        
        # Add export-friendly format
        result["exportable"] = {
            "ingredients": [
                {"name": ing["name"], "grams": ing["grams"]}
                for ing in result["ingredients"]
                if "error" not in ing
            ],
            "totals": result["recipe_totals"]
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================
# Label Tools
# ============================================

@tool
def format_nutrition_label(nutrition_json: str, food_name: str) -> str:
    """
    Create a text-based nutrition label.
    
    Args:
        nutrition_json: JSON string with nutrition data from get_nutrition
        food_name: Name of the food for the label header
    
    Returns:
        Formatted text nutrition label
    """
    try:
        data = json.loads(nutrition_json)
        if isinstance(data, list):
            data = data[0]
        return _get_label_service().format_text(data, food_name)
    except Exception as e:
        return f"Error creating label: {e}"


@tool
def generate_label_image(nutrition_json: str, food_name: str) -> str:
    """
    Generate a visual FDA-style nutrition label image.
    
    Args:
        nutrition_json: JSON string with nutrition data from get_nutrition
        food_name: Name of the food for the label
    
    Returns:
        Confirmation message with filename. Image is saved and can be accessed via API.
    """
    try:
        data = json.loads(nutrition_json)
        if isinstance(data, list):
            data = data[0]
        
        # Generate image bytes
        image_bytes = _get_label_service().generate_image(data, food_name)
        
        # Save locally (API will serve it)
        from pathlib import Path
        labels_dir = Path(__file__).parent.parent / "data" / "labels"
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in food_name)[:30]
        filename = f"{safe_name}_{timestamp}.png"
        
        filepath = labels_dir / filename
        filepath.write_bytes(image_bytes)
        
        return f"✅ Nutrition label saved as '{filename}'. Access at /labels/{filename}"
        
    except Exception as e:
        return f"Error generating image: {e}"


# ============================================
# Export all tools
# ============================================

def get_all_tools() -> list:
    """Return all available tools."""
    return [
        search_foods,
        get_nutrition,
        calculate_recipe_nutrition,
        format_nutrition_label,
        generate_label_image,
    ]
