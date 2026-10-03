# tests/test_unit_converter.py
"""Tests for UnitConverter."""

import pytest
from backend.services.unit_converter import UnitConverter


def test_direct_weight_conversion():
    res = UnitConverter.resolve_to_grams(100, "g", "flour")
    assert res["grams"] == 100.0
    assert res["source"] == "direct_weight"

    res_oz = UnitConverter.resolve_to_grams(2, "oz", "cheese")
    assert abs(res_oz["grams"] - 56.7) < 0.1

    res_lb = UnitConverter.resolve_to_grams(1, "lb", "beef")
    assert abs(res_lb["grams"] - 453.6) < 0.1


def test_volumetric_density_conversion():
    # Olive oil: density 0.92 g/ml. 1 tbsp = 14.787 ml -> ~13.6g
    oil_res = UnitConverter.resolve_to_grams(1, "tbsp", "olive oil")
    assert abs(oil_res["grams"] - 13.6) < 0.5
    assert oil_res["source"] == "volumetric_density"

    # Oats: density ~0.38 g/ml. 1 cup = 236.59 ml -> ~89.9g
    oats_res = UnitConverter.resolve_to_grams(1, "cup", "rolled oats")
    assert abs(oats_res["grams"] - 89.9) < 2.0


def test_discrete_count_conversion():
    # 2 eggs: 50g each = 100g
    egg_res = UnitConverter.resolve_to_grams(2, None, "large egg")
    assert egg_res["grams"] == 100.0
    assert egg_res["source"] == "discrete_food_count"

    # 1 medium banana = 118g
    banana_res = UnitConverter.resolve_to_grams(1, "medium", "banana")
    assert banana_res["grams"] == 118.0

    # 3 cloves garlic = 9g
    garlic_res = UnitConverter.resolve_to_grams(3, "clove", "garlic")
    assert garlic_res["grams"] == 9.0


def test_usda_portion_matching():
    portions = [
        {"description": "1 cup, rolled", "gram_weight": 81.0, "amount": 1.0, "unit": "cup"},
        {"description": "1 tbsp", "gram_weight": 5.0, "amount": 1.0, "unit": "tbsp"},
    ]

    res = UnitConverter.resolve_to_grams(2, "cup", "oats", usda_portions=portions)
    assert res["grams"] == 162.0
    assert res["source"] == "usda_portion"


def test_zero_or_negative_quantity():
    res = UnitConverter.resolve_to_grams(0, "cup", "milk")
    assert res["grams"] == 0.0
