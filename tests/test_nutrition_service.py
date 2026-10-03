# tests/test_nutrition_service.py
"""Tests for NutritionService concurrent calculations."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.nutrition import NutritionService
from backend.services.cache import SQLiteCache


@pytest.fixture
def mock_usda_client():
    client = MagicMock()
    # Mock search_async
    client.search_async = AsyncMock(side_effect=lambda q: [
        {"fdcId": 1001, "description": f"{q.title()} Item"}
    ])
    # Mock get_food_async
    client.get_food_async = AsyncMock(side_effect=lambda fid: {
        "fdcId": fid,
        "description": f"Food {fid}",
        "foodNutrients": [
            {"nutrient": {"id": 1008}, "amount": 200.0},  # calories
            {"nutrient": {"id": 1003}, "amount": 10.0},   # protein
            {"nutrient": {"id": 1005}, "amount": 30.0},   # carbs
            {"nutrient": {"id": 1004}, "amount": 5.0},    # fat
        ],
        "foodPortions": [
            {"portionDescription": "1 cup", "gramWeight": 150.0, "amount": 1.0}
        ]
    })
    return client


@pytest.fixture
def test_service(tmp_path, mock_usda_client):
    cache = SQLiteCache(db_path=str(tmp_path / "test_nutrition.db"), migrate_legacy=False)
    return NutritionService(client=mock_usda_client, cache=cache)


@pytest.mark.asyncio
async def test_calculate_recipe_async_concurrency(test_service):
    ingredients = [
        {"name": "oats", "grams": 100},
        {"name": "milk", "grams": 200},
        {"name": "berries", "grams": 50},
    ]

    result = await test_service.calculate_recipe_async(ingredients)

    assert "recipe_totals" in result
    assert "ingredients" in result
    assert len(result["ingredients"]) == 3

    # Check totals:
    # oats: 100g = 1x base -> 200 cal
    # milk: 200g = 2x base -> 400 cal
    # berries: 50g = 0.5x base -> 100 cal
    # Total calories = 700 cal
    assert result["recipe_totals"]["calories"] == 700.0
    assert result["recipe_totals"]["protein"] == 35.0  # 10 + 20 + 5

    # Check that portion metadata was captured
    for ing in result["ingredients"]:
        assert len(ing["portions"]) == 1
        assert ing["portions"][0]["description"] == "1 cup"
        assert ing["portions"][0]["gram_weight"] == 150.0
