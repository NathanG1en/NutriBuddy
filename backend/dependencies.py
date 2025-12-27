# backend/dependencies.py
"""Factory functions for dependency injection."""

from functools import lru_cache
from backend.services.nutrition import NutritionService
from backend.services.labels import LabelService
from backend.agent.graph import NutritionAgent  # ← Changed import


@lru_cache
def get_nutrition_service() -> NutritionService:
    return NutritionService()


@lru_cache
def get_label_service() -> LabelService:
    return LabelService()


@lru_cache
def get_agent() -> NutritionAgent:
    return NutritionAgent()
