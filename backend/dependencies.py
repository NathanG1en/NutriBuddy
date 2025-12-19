# backend/dependencies.py
"""Factory functions to create configured instances."""

from functools import lru_cache
from backend.services.nutrition import NutritionService
from backend.services.labels import LabelService
from backend.agent.graph import create_agent

@lru_cache
def get_nutrition_service() -> NutritionService:
    return NutritionService()

@lru_cache
def get_label_service() -> LabelService:
    return LabelService()

@lru_cache
def get_agent():
    return create_agent()