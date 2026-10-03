# backend/services/nutrition.py
"""
Nutrition service - orchestrates food search, nutrient extraction,
and high-concurrency recipe nutrition calculations.
"""

import asyncio
from typing import Optional
from backend.services.usda_client import USDAClient
from backend.services.food_matcher import FoodMatcher
from backend.services.cache import FileCache
from backend.config import settings


class NutritionService:
    """Main entry point for nutrition operations, supporting both async and sync workflows."""

    NUTRIENT_MAP = {
        1008: "calories",
        1003: "protein",
        1005: "carbs",
        1004: "fat",
        1258: "sat_fat",
        1257: "trans_fat",
        1079: "fiber",
        2000: "sugars",
        1235: "added_sugars",
        1093: "sodium",
        1253: "cholesterol",
        1114: "vit_d",
        1087: "calcium",
        1089: "iron",
        1092: "potassium",
    }

    TOTAL_KEYS = [
        "calories",
        "protein",
        "carbs",
        "fat",
        "sat_fat",
        "trans_fat",
        "fiber",
        "sugars",
        "added_sugars",
        "sodium",
        "cholesterol",
        "vit_d",
        "calcium",
        "iron",
        "potassium",
    ]

    def __init__(
        self,
        client: USDAClient | None = None,
        matcher: FoodMatcher | None = None,
        cache: FileCache | None = None,
    ):
        self._client = client or USDAClient(settings.USDA_KEY)
        self._matcher = matcher or FoodMatcher()
        self._cache = cache or FileCache()

    # ============================================
    # Asynchronous Operations
    # ============================================

    async def search_async(self, query: str) -> Optional[dict]:
        """Asynchronously search for a food and return the best match."""
        cache_key = f"search:{query.strip().lower()}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        results = await self._client.search_async(query)
        if not results:
            return None

        best = self._matcher.find_best_match(query, results)
        if best:
            self._cache.set(cache_key, best)

        return best

    async def get_nutrition_async(self, fdc_id: int) -> Optional[dict]:
        """Asynchronously get detailed nutrition data for a food."""
        cache_key = f"nutrition:{fdc_id}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        data = await self._client.get_food_async(fdc_id)
        if data:
            nutrition = self._extract_nutrients(data)
            self._cache.set(cache_key, nutrition)
            return nutrition

        return None

    async def calculate_recipe_async(self, ingredients: list[dict]) -> dict:
        """
        Calculate combined nutrition for a recipe concurrently.
        Executes search and nutrient retrieval in parallel across all ingredients.

        Args:
            ingredients: List of {"name": "flour", "grams": 100}

        Returns:
            {"recipe_totals": {...}, "ingredients": [...]}
        """
        totals = {key: 0.0 for key in self.TOTAL_KEYS}

        async def _resolve_ingredient(ing: dict) -> dict:
            name = ing.get("name", "")
            grams = ing.get("grams", 100)

            # 1. Search for food item
            result = await self.search_async(name)
            if not result:
                return {
                    "name": name,
                    "grams": grams,
                    "error": "Not found in database",
                }

            fdc_id = result.get("fdcId")
            if not fdc_id:
                return {
                    "name": name,
                    "grams": grams,
                    "error": "Invalid food record",
                }

            # 2. Fetch nutrition
            nutrition = await self.get_nutrition_async(int(fdc_id))
            if not nutrition:
                return {
                    "name": name,
                    "grams": grams,
                    "error": "No nutrition data",
                }

            # 3. Scale by grams (nutrition base is per 100g)
            scale = grams / 100.0
            scaled: dict[str, float] = {}
            for key in self.TOTAL_KEYS:
                value = nutrition.get(key, 0.0) * scale
                scaled[key] = round(value, 2)

            return {
                "name": name,
                "description": nutrition.get("name", name),
                "grams": grams,
                "fdc_id": fdc_id,
                "nutrition": scaled,
                "portions": nutrition.get("portions", []),
            }

        # Resolve all ingredients concurrently
        ingredient_details = await asyncio.gather(
            *[_resolve_ingredient(ing) for ing in ingredients]
        )

        # Aggregate totals from successfully resolved ingredients
        for item in ingredient_details:
            if "error" not in item:
                item_nutrition = item.get("nutrition", {})
                for key in self.TOTAL_KEYS:
                    totals[key] += item_nutrition.get(key, 0.0)

        # Round totals
        for key in totals:
            totals[key] = round(totals[key], 2)

        return {
            "recipe_totals": totals,
            "ingredients": list(ingredient_details),
        }

    # ============================================
    # Synchronous Operations (Compatibility)
    # ============================================

    def search(self, query: str) -> Optional[dict]:
        """Synchronously search for a food and return best match."""
        cache_key = f"search:{query.strip().lower()}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        results = self._client.search(query)
        if not results:
            return None

        best = self._matcher.find_best_match(query, results)
        if best:
            self._cache.set(cache_key, best)

        return best

    def get_nutrition(self, fdc_id: int) -> Optional[dict]:
        """Synchronously get nutrition data for a food."""
        cache_key = f"nutrition:{fdc_id}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        data = self._client.get_food(fdc_id)
        if data:
            nutrition = self._extract_nutrients(data)
            self._cache.set(cache_key, nutrition)
            return nutrition

        return None

    def calculate_recipe(self, ingredients: list[dict]) -> dict:
        """Synchronous recipe calculation (delegates to async run if loop not running)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already inside an event loop (e.g. nested call), run synchronously step-by-step
            totals = {key: 0.0 for key in self.TOTAL_KEYS}
            ingredient_details = []
            for ing in ingredients:
                name = ing.get("name", "")
                grams = ing.get("grams", 100)
                result = self.search(name)
                if not result:
                    ingredient_details.append(
                        {"name": name, "grams": grams, "error": "Not found in database"}
                    )
                    continue
                fdc_id = result.get("fdcId")
                nutrition = self.get_nutrition(fdc_id)
                if not nutrition:
                    ingredient_details.append(
                        {"name": name, "grams": grams, "error": "No nutrition data"}
                    )
                    continue
                scale = grams / 100.0
                scaled = {
                    key: round(nutrition.get(key, 0.0) * scale, 2)
                    for key in self.TOTAL_KEYS
                }
                for key in self.TOTAL_KEYS:
                    totals[key] += scaled[key]
                ingredient_details.append(
                    {
                        "name": name,
                        "description": nutrition.get("name", name),
                        "grams": grams,
                        "fdc_id": fdc_id,
                        "nutrition": scaled,
                        "portions": nutrition.get("portions", []),
                    }
                )
            for key in totals:
                totals[key] = round(totals[key], 2)
            return {"recipe_totals": totals, "ingredients": ingredient_details}

        return asyncio.run(self.calculate_recipe_async(ingredients))

    # ============================================
    # Parsing Helpers
    # ============================================

    def _extract_nutrients(self, raw: dict) -> dict:
        """Extract key FDA nutrients and standard portion sizes from USDA response."""
        result = {
            "name": raw.get("description", "Unknown"),
            "fdc_id": raw.get("fdcId"),
        }

        # Initialize defaults
        for field_name in self.TOTAL_KEYS:
            result[field_name] = 0.0

        for nutrient in raw.get("foodNutrients", []):
            nid = nutrient.get("nutrient", {}).get("id")
            if nid in self.NUTRIENT_MAP:
                key = self.NUTRIENT_MAP[nid]
                result[key] = float(nutrient.get("amount", 0.0))

        # Extract standard portion sizes if present
        portions = []
        for p in raw.get("foodPortions", []):
            gram_weight = p.get("gramWeight")
            if gram_weight:
                desc = (
                    p.get("portionDescription")
                    or p.get("modifier")
                    or f"{p.get('amount', 1.0)} {p.get('measureUnit', {}).get('name', 'serving')}"
                )
                portions.append(
                    {
                        "description": desc.strip(),
                        "gram_weight": round(float(gram_weight), 2),
                        "amount": p.get("amount", 1.0),
                        "unit": p.get("measureUnit", {}).get("name"),
                    }
                )

        result["portions"] = portions
        return result