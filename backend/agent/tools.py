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
def parse_recipe_text(recipe_text: str) -> str:
    """
    Parse unstructured recipe text into structured ingredients with quantities, units, and food names.

    Args:
        recipe_text: The recipe ingredients text (e.g. "2 cups rolled oats\n1 cup whole milk\n2 tbsp chia seeds")

    Returns:
        JSON list of parsed ingredients with food name, quantity, and culinary unit.
    """
    try:
        from backend.services.ingredient_parser import IngredientParser
        parsed = IngredientParser.parse_recipe_text(recipe_text)
        return json.dumps([p.model_dump() for p in parsed], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def calculate_recipe_nutrition(ingredients_input: str) -> str:
    """
    Calculate combined nutrition for a recipe with multiple ingredients.
    Accepts natural language measurements (e.g. cups, tbsp, oz, slices, grams) or JSON.

    Args:
        ingredients_input: Either:
            1. Multi-line string, e.g.: "2 cups rolled oats\n1 cup milk\n2 tbsp peanut butter"
            2. JSON array of strings: ["2 cups rolled oats", "1 cup milk"]
            3. JSON array of objects: [{"name": "oats", "quantity": 2, "unit": "cup"}]

    Returns:
        JSON with total nutrition, per-ingredient breakdown, and resolved gram weights.
    """
    try:
        service = _get_nutrition_service()
        # Check if input is valid JSON
        try:
            parsed_json = json.loads(ingredients_input)
            if isinstance(parsed_json, list):
                result = service.calculate_recipe(parsed_json)
            else:
                result = service.calculate_recipe([parsed_json])
        except (json.JSONDecodeError, TypeError):
            # Treat as multi-line natural language text
            from backend.services.ingredient_parser import IngredientParser
            parsed_items = IngredientParser.parse_recipe_text(ingredients_input)
            items = [
                {"name": p.food_name, "quantity": p.quantity, "unit": p.unit, "raw_text": p.raw_text}
                for p in parsed_items
            ]
            result = service.calculate_recipe(items)

        # Add export-friendly format
        result["exportable"] = {
            "ingredients": [
                {"name": ing["name"], "grams": ing.get("grams", 0.0)}
                for ing in result["ingredients"]
                if "error" not in ing
            ],
            "totals": result["recipe_totals"],
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
        parse_recipe_text,
        calculate_recipe_nutrition,
        format_nutrition_label,
        generate_label_image,
    ]
