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
        # Allow dependency injection, but provide defaults
        self._client = client or USDAClient(settings.USDA_KEY)
        self._matcher = matcher or FoodMatcher()
        self._cache = cache or FileCache()

    def search(self, query: str) -> dict | None:
        """Search for a food and return best match."""
        # Check cache first
        cached = self._cache.get(f"search:{query}")
        if cached:
            return cached

        # Search USDA
        results = self._client.search(query)
        if not results:
            return None

        # Find best match
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
            # Extract and normalize nutrients
            nutrition = self._extract_nutrients(data)
            self._cache.set(f"nutrition:{fdc_id}", nutrition)
            return nutrition

        return None

    def _extract_nutrients(self, raw: dict) -> dict:
        """Extract key nutrients from USDA response."""
        # Mapping of nutrient IDs to friendly names
        nutrient_map = {
            1008: "calories",
            1003: "protein",
            1005: "carbs",
            1004: "fat",
            1079: "fiber",
            2000: "sugars",
            1093: "sodium",
        }

        result = {"name": raw.get("description", "Unknown")}

        for nutrient in raw.get("foodNutrients", []):
            nid = nutrient.get("nutrient", {}).get("id")
            if nid in nutrient_map:
                result[nutrient_map[nid]] = nutrient.get("amount", 0)

        return result