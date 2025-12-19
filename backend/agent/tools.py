# backend/agent/tools.py
"""
Agent tools - thin wrappers that delegate to services.

For now, these return mock data. Replace with real service calls later.
"""

from langchain_core.tools import tool


@tool
def search_foods(query: str) -> str:
    """
    Search for foods in the USDA database.

    Args:
        query: Food name to search for (e.g., "avocado", "chicken breast")

    Returns:
        JSON with matching foods and their FDC IDs
    """
    # TODO: Replace with real service call
    # service = get_nutrition_service()
    # return service.search(query)

    import json

    # Mock response for now
    mock_results = {
        "query": query,
        "results": [
            {"fdc_id": "123456", "description": f"{query.title()}, raw", "brand": "Generic"},
            {"fdc_id": "123457", "description": f"{query.title()}, cooked", "brand": "Generic"},
        ]
    }
    return json.dumps(mock_results, indent=2)


@tool
def get_nutrition(fdc_id: str) -> str:
    """
    Get detailed nutrition data for a food by its FDC ID.

    Args:
        fdc_id: The FDC ID from search results (e.g., "123456")

    Returns:
        JSON with nutrition facts (calories, protein, carbs, fat, etc.)
    """
    # TODO: Replace with real service call

    import json

    # Mock response
    mock_nutrition = {
        "fdc_id": fdc_id,
        "description": "Sample Food",
        "serving_size": "100g",
        "nutrients": {
            "calories": 150,
            "protein_g": 12.5,
            "carbs_g": 8.2,
            "fat_g": 9.1,
            "fiber_g": 2.3,
            "sodium_mg": 45
        }
    }
    return json.dumps(mock_nutrition, indent=2)


@tool
def compare_nutrients(fdc_ids: str, nutrient: str) -> str:
    """
    Compare a specific nutrient across multiple foods.

    Args:
        fdc_ids: Comma-separated FDC IDs (e.g., "123456,789012")
        nutrient: Nutrient to compare (e.g., "protein", "calories", "fat")

    Returns:
        Comparison table showing the nutrient for each food
    """
    # TODO: Replace with real service call

    import json

    ids = [id.strip() for id in fdc_ids.split(",")]

    # Mock comparison
    comparison = {
        "nutrient": nutrient,
        "comparison": [
            {"fdc_id": id, "food": f"Food {id}", nutrient: f"{10 + i * 5}g"}
            for i, id in enumerate(ids)
        ]
    }
    return json.dumps(comparison, indent=2)


@tool
def generate_label(food_name: str, calories: int, protein: float, carbs: float, fat: float) -> str:
    """
    Generate a nutrition label for a food item.

    Args:
        food_name: Name of the food
        calories: Calories per serving
        protein: Protein in grams
        carbs: Carbohydrates in grams
        fat: Fat in grams

    Returns:
        Path to the generated label image or formatted text label
    """
    # TODO: Replace with real label generation

    label = f"""
╔══════════════════════════════╗
║      NUTRITION FACTS         ║
╠══════════════════════════════╣
║  {food_name[:26]:<26}  ║
╠══════════════════════════════╣
║  Serving Size: 100g          ║
╠══════════════════════════════╣
║  Calories: {calories:<18} ║
║  Total Fat: {fat:.1f}g{'':<14} ║
║  Total Carbs: {carbs:.1f}g{'':<11} ║
║  Protein: {protein:.1f}g{'':<14} ║
╚══════════════════════════════╝
"""
    return label


def get_all_tools() -> list:
    """Return all available tools."""
    return [
        search_foods,
        get_nutrition,
        compare_nutrients,
        generate_label
    ]