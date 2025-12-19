# backend/services/nutrition.py
class NutritionService:
    """Handles food search and nutrition data retrieval."""

    def search(self, query: str) -> list[dict]:
        """Search USDA database."""
        pass

    def get_nutrition(self, fdc_ids: list[str]) -> dict:
        """Fetch nutrition data."""
        pass

    def compare(self, fdc_ids: list[str], nutrient: str) -> dict:
        """Compare nutrients across foods."""
        pass