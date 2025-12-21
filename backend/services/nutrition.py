# backend/services/nutrition.py
"""Nutrition service - orchestrates search and data retrieval."""

from backend.services.usda_client import USDAClient
from backend.services.food_matcher import FoodMatcher
from backend.services.cache import FileCache
from backend.config import settings


class NutritionService:
    """Main entry point for nutrition operations."""

    def __init__(
            self,
            client: USDAClient | None = None,
            matcher: FoodMatcher | None = None,
            cache: FileCache | None = None
    ):
        self._client = client or USDAClient(settings.USDA_KEY)
        self._matcher = matcher or FoodMatcher()
        self._cache = cache or FileCache()

    def search(self, query: str) -> dict | None:
        """Search for a food and return best match."""
        cached = self._cache.get(f"search:{query}")
        if cached:
            return cached

        results = self._client.search(query)
        if not results:
            return None

        best = self._matcher.find_best_match(query, results)
        if best:
            self._cache.set(f"search:{query}", best)

        return best

    def get_nutrition(self, fdc_id: int) -> dict | None:
        """Get nutrition data for a food."""
        cached = self._cache.get(f"nutrition:{fdc_id}")
        if cached:
            return cached

        data = self._client.get_food(fdc_id)
        if data:
            nutrition = self._extract_nutrients(data)
            self._cache.set(f"nutrition:{fdc_id}", nutrition)
            return nutrition

        return None

    def calculate_recipe(self, ingredients: list[dict]) -> dict:
        """
        Calculate combined nutrition for a recipe.
        
        Args:
            ingredients: List of {"name": "flour", "grams": 100}
        
        Returns:
            {"recipe_totals": {...}, "ingredients": [...]}
        """
        totals = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "fiber": 0,
            "sugars": 0,
            "sodium": 0,
            "cholesterol": 0,
        }
        
        ingredient_details = []
        
        for ing in ingredients:
            name = ing.get("name", "")
            grams = ing.get("grams", 100)
            
            # Search for the food
            result = self.search(name)
            if not result:
                ingredient_details.append({
                    "name": name,
                    "grams": grams,
                    "error": "Not found in database"
                })
                continue
            
            # Get nutrition (per 100g)
            fdc_id = result.get("fdcId")
            nutrition = self.get_nutrition(fdc_id)
            if not nutrition:
                ingredient_details.append({
                    "name": name,
                    "grams": grams,
                    "error": "No nutrition data"
                })
                continue
            
            # Scale by grams (nutrition data is per 100g)
            scale = grams / 100
            
            scaled = {}
            for key in totals:
                value = nutrition.get(key, 0) * scale
                scaled[key] = round(value, 2)
                totals[key] += value
            
            ingredient_details.append({
                "name": name,
                "grams": grams,
                "fdc_id": fdc_id,
                "nutrition": scaled
            })
        
        # Round totals
        for key in totals:
            totals[key] = round(totals[key], 2)
        
        return {
            "recipe_totals": totals,
            "ingredients": ingredient_details
        }

    def _extract_nutrients(self, raw: dict) -> dict:
        """Extract key nutrients from USDA response."""
        nutrient_map = {
            1008: "calories",
            1003: "protein",
            1005: "carbs",
            1004: "fat",
            1079: "fiber",
            2000: "sugars",
            1093: "sodium",
            1253: "cholesterol",
        }

        result = {"name": raw.get("description", "Unknown")}

        for nutrient in raw.get("foodNutrients", []):
            nid = nutrient.get("nutrient", {}).get("id")
            if nid in nutrient_map:
                result[nutrient_map[nid]] = nutrient.get("amount", 0)

        return result