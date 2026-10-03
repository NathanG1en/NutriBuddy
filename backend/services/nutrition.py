# backend/services/nutrition.py
"""
Nutrition service - orchestrates food search, nutrient extraction,
natural language unit conversion, and high-concurrency recipe nutrition calculations.
"""

import asyncio
from typing import Optional, Union, List
from backend.services.usda_client import USDAClient
from backend.services.food_matcher import FoodMatcher
from backend.services.cache import FileCache
from backend.services.ingredient_parser import IngredientParser, ParsedIngredient
from backend.services.unit_converter import UnitConverter
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

    async def calculate_recipe_async(
        self, ingredients: List[Union[dict, str]]
    ) -> dict:
        """
        Calculate combined nutrition for a recipe concurrently.
        Supports natural language strings (e.g. "2 cups oats"), structured objects
        with quantities and units, or legacy objects with explicit grams.

        Args:
            ingredients: List of items, e.g.:
                - "2 1/2 cups rolled oats"
                - {"name": "rolled oats", "quantity": 2.5, "unit": "cup"}
                - {"name": "flour", "grams": 200}
                - {"raw_text": "2 large eggs"}

        Returns:
            {"recipe_totals": {...}, "ingredients": [...]}
        """
        totals = {key: 0.0 for key in self.TOTAL_KEYS}

        async def _resolve_ingredient(ing: Union[dict, str]) -> dict:
            explicit_grams = None
            quantity = 1.0
            unit = None

            # 1. Normalize and parse ingredient input
            if isinstance(ing, str):
                parsed = IngredientParser.parse_line(ing)
                food_query = parsed.food_name
                quantity = parsed.quantity
                unit = parsed.unit
                raw_text = ing
            elif isinstance(ing, dict) and ("raw_text" in ing or "text" in ing):
                raw_text = ing.get("raw_text") or ing.get("text", "")
                parsed = IngredientParser.parse_line(raw_text)
                food_query = parsed.food_name
                quantity = parsed.quantity
                unit = parsed.unit
            elif isinstance(ing, dict):
                food_query = ing.get("name", "")
                quantity = float(ing.get("quantity") or 1.0)
                unit = ing.get("unit")
                raw_text = f"{quantity} {unit or ''} {food_query}".strip()
                # Check for explicit grams specification
                if "grams" in ing and ing["grams"] is not None and not unit:
                    explicit_grams = float(ing["grams"])
            else:
                return {"name": str(ing), "grams": 0.0, "error": "Invalid format"}

            if not food_query:
                return {"name": raw_text, "grams": 0.0, "error": "Missing food name"}

            # 2. Search for food item in USDA database
            result = await self.search_async(food_query)
            if not result:
                return {
                    "name": food_query,
                    "raw_text": raw_text,
                    "grams": 0.0,
                    "error": "Not found in database",
                }

            fdc_id = result.get("fdcId")
            if not fdc_id:
                return {
                    "name": food_query,
                    "raw_text": raw_text,
                    "grams": 0.0,
                    "error": "Invalid food record",
                }

            # 3. Fetch nutrition profile and USDA portions
            nutrition = await self.get_nutrition_async(int(fdc_id))
            if not nutrition:
                return {
                    "name": food_query,
                    "raw_text": raw_text,
                    "grams": 0.0,
                    "error": "No nutrition data",
                }

            # 4. Resolve culinary quantity and unit into gram weight
            if explicit_grams is not None:
                resolved_grams = explicit_grams
                conversion_info = {
                    "grams": explicit_grams,
                    "source": "explicit_grams",
                    "matched_portion": f"{explicit_grams}g",
                }
            else:
                usda_portions = nutrition.get("portions", [])
                conversion_info = UnitConverter.resolve_to_grams(
                    quantity=quantity,
                    unit=unit,
                    food_name=food_query,
                    usda_portions=usda_portions,
                )
                resolved_grams = conversion_info["grams"]

            # 5. Scale nutrition by (grams / 100g base)
            scale = resolved_grams / 100.0 if resolved_grams > 0 else 0.0
            scaled: dict[str, float] = {}
            for key in self.TOTAL_KEYS:
                value = nutrition.get(key, 0.0) * scale
                scaled[key] = round(value, 2)

            return {
                "name": food_query,
                "description": nutrition.get("name", food_query),
                "raw_text": raw_text,
                "quantity": quantity,
                "unit": unit,
                "grams": resolved_grams,
                "conversion_source": conversion_info.get("source"),
                "matched_portion": conversion_info.get("matched_portion"),
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

    async def calculate_recipe_text_async(self, text: str) -> dict:
        """
        Parse multi-line recipe text and calculate combined nutrition concurrently.
        """
        parsed_ingredients = IngredientParser.parse_recipe_text(text)
        return await self.calculate_recipe_async([
            {
                "name": p.food_name,
                "quantity": p.quantity,
                "unit": p.unit,
                "raw_text": p.raw_text,
            }
            for p in parsed_ingredients
        ])

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

    def calculate_recipe(self, ingredients: List[Union[dict, str]]) -> dict:
        """Synchronous recipe calculation (delegates to async run if loop not running)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already inside an active loop, execute synchronously
            totals = {key: 0.0 for key in self.TOTAL_KEYS}
            ingredient_details = []
            for ing in ingredients:
                if isinstance(ing, str):
                    parsed = IngredientParser.parse_line(ing)
                    name = parsed.food_name
                    qty = parsed.quantity
                    unit = parsed.unit
                    raw_text = ing
                    explicit_grams = None
                elif isinstance(ing, dict):
                    name = ing.get("name", "")
                    qty = float(ing.get("quantity") or 1.0)
                    unit = ing.get("unit")
                    raw_text = ing.get("raw_text") or f"{qty} {unit or ''} {name}".strip()
                    explicit_grams = ing.get("grams") if not unit else None
                else:
                    continue

                result = self.search(name)
                if not result:
                    ingredient_details.append({"name": name, "grams": 0.0, "error": "Not found in database"})
                    continue
                fdc_id = result.get("fdcId")
                nutrition = self.get_nutrition(fdc_id)
                if not nutrition:
                    ingredient_details.append({"name": name, "grams": 0.0, "error": "No nutrition data"})
                    continue

                if explicit_grams is not None:
                    resolved_grams = float(explicit_grams)
                    conversion_info = {"source": "explicit_grams", "matched_portion": f"{resolved_grams}g"}
                else:
                    conversion_info = UnitConverter.resolve_to_grams(
                        qty, unit, name, nutrition.get("portions", [])
                    )
                    resolved_grams = conversion_info["grams"]

                scale = resolved_grams / 100.0 if resolved_grams > 0 else 0.0
                scaled = {k: round(nutrition.get(k, 0.0) * scale, 2) for k in self.TOTAL_KEYS}
                for k in self.TOTAL_KEYS:
                    totals[k] += scaled[k]

                ingredient_details.append({
                    "name": name,
                    "description": nutrition.get("name", name),
                    "raw_text": raw_text,
                    "grams": resolved_grams,
                    "conversion_source": conversion_info.get("source"),
                    "matched_portion": conversion_info.get("matched_portion"),
                    "fdc_id": fdc_id,
                    "nutrition": scaled,
                    "portions": nutrition.get("portions", []),
                })

            for k in totals:
                totals[k] = round(totals[k], 2)
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