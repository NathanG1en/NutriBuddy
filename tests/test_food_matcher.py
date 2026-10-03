# tests/test_food_matcher.py
"""Tests for two-stage FoodMatcher."""

import pytest
from backend.services.food_matcher import FoodMatcher


@pytest.fixture(scope="module")
def matcher():
    return FoodMatcher()


def test_empty_candidates(matcher):
    assert matcher.find_best_match("banana", []) is None


def test_single_candidate(matcher):
    candidates = [{"description": "Banana, raw", "fdcId": 101}]
    result = matcher.find_best_match("banana", candidates)
    assert result == candidates[0]


def test_exact_match_fast_path(matcher):
    candidates = [
        {"description": "Whole Milk, 3.25%", "fdcId": 201},
        {"description": "Rolled Oats", "fdcId": 202},
        {"description": "Almond Butter", "fdcId": 203},
    ]
    result = matcher.find_best_match("Rolled Oats", candidates)
    assert result is not None
    assert result["fdcId"] == 202


def test_hybrid_matching_relevance(matcher):
    candidates = [
        {"description": "Candy Chocolate Bar with Almonds", "fdcId": 301},
        {"description": "Whole Grain Rolled Oats, dry", "fdcId": 302},
        {"description": "Boneless Chicken Breast, raw", "fdcId": 303},
        {"description": "Instant Oatmeal, flavored maple", "fdcId": 304},
    ]
    result = matcher.find_best_match("rolled oats", candidates)
    assert result is not None
    assert result["fdcId"] == 302
