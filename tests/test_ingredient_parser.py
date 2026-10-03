# tests/test_ingredient_parser.py
"""Tests for IngredientParser."""

import pytest
from backend.services.ingredient_parser import IngredientParser


def test_parse_fractions():
    # Simple fraction
    qty, rem = IngredientParser.parse_quantity("1/2 cup milk")
    assert qty == 0.5
    assert rem == "cup milk"

    # Mixed fraction
    qty, rem = IngredientParser.parse_quantity("2 1/2 cups flour")
    assert qty == 2.5
    assert rem == "cups flour"

    # Unicode fraction
    qty, rem = IngredientParser.parse_quantity("¾ tsp baking powder")
    assert qty == 0.75

    # Range
    qty, rem = IngredientParser.parse_quantity("2-3 apples")
    assert qty == 2.5


def test_parse_line_variations():
    p1 = IngredientParser.parse_line("2 1/2 cups rolled oats")
    assert p1.quantity == 2.5
    assert p1.unit == "cups"
    assert p1.food_name == "rolled oats"

    p2 = IngredientParser.parse_line("2 tbsp olive oil (extra virgin)")
    assert p2.quantity == 2.0
    assert p2.unit == "tbsp"
    assert p2.food_name == "olive oil"
    assert p2.preparation == "extra virgin"

    p3 = IngredientParser.parse_line("1 medium onion, finely chopped")
    assert p3.quantity == 1.0
    assert p3.unit == "medium"
    assert p3.food_name == "onion"
    assert "finely chopped" in p3.preparation

    p4 = IngredientParser.parse_line("pinch of sea salt")
    assert p4.quantity == 1.0
    assert p4.unit == "pinch"
    assert p4.food_name == "sea salt"


def test_parse_recipe_multi_line():
    recipe = """
    Ingredients:
    - 2 cups rolled oats
    - 1 cup whole milk
    - 2 tbsp peanut butter
    - 1 medium banana
    """
    items = IngredientParser.parse_recipe_text(recipe)
    assert len(items) == 4
    assert items[0].food_name == "rolled oats"
    assert items[0].quantity == 2.0
    assert items[1].food_name == "whole milk"
    assert items[2].food_name == "peanut butter"
    assert items[3].food_name == "banana"
