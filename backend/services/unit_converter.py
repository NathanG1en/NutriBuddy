# backend/services/unit_converter.py
"""
Culinary unit conversion and USDA portion resolution engine.
Maps arbitrary natural language cooking units (cups, tbsp, slices, ounces)
to accurate gram weights using USDA foodPortions and culinary density models.
"""

import logging
import re
from typing import Optional
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# Standard exact mass conversions to grams
WEIGHT_UNITS_TO_GRAMS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "mg": 0.001,
    "milligram": 0.001,
    "milligrams": 0.001,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "lbs": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
}

# Standard volumetric conversions to milliliters (ml)
VOLUME_UNITS_TO_ML = {
    "tsp": 4.92892,
    "teaspoon": 4.92892,
    "teaspoons": 4.92892,
    "tbsp": 14.7868,
    "tbs": 14.7868,
    "tablespoon": 14.7868,
    "tablespoons": 14.7868,
    "fl oz": 29.5735,
    "fluid ounce": 29.5735,
    "fluid ounces": 29.5735,
    "cup": 236.588,
    "cups": 236.588,
    "c": 236.588,
    "pt": 473.176,
    "pint": 473.176,
    "pints": 473.176,
    "qt": 946.353,
    "quart": 946.353,
    "quarts": 946.353,
    "gal": 3785.41,
    "gallon": 3785.41,
    "gallons": 3785.41,
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "pinch": 0.36,
    "dash": 0.72,
    "drop": 0.05,
    "drops": 0.05,
}

# Common culinary density approximations (grams per ml) by ingredient keyword
CULINARY_DENSITIES = {
    # Liquids / Dairy / Syrups
    "water": 1.0,
    "milk": 1.03,
    "cream": 1.01,
    "buttermilk": 1.03,
    "oil": 0.92,
    "olive oil": 0.92,
    "honey": 1.42,
    "maple syrup": 1.33,
    "molasses": 1.41,
    "vinegar": 1.01,
    "soy sauce": 1.15,
    "broth": 1.0,
    "juice": 1.04,
    # Powders / Dry Goods (lower bulk density)
    "flour": 0.53,  # 1 cup ~ 125g
    "all-purpose flour": 0.53,
    "almond flour": 0.45,
    "sugar": 0.85,  # 1 cup ~ 200g
    "granulated sugar": 0.85,
    "brown sugar": 0.83,  # 1 cup packed ~ 200g
    "powdered sugar": 0.50,  # 1 cup ~ 120g
    "oats": 0.38,  # 1 cup ~ 85g-90g
    "rolled oats": 0.38,
    "oatmeal": 0.38,
    "cocoa": 0.42,  # 1 cup ~ 100g
    "cocoa powder": 0.42,
    "chia": 0.75,
    "chia seeds": 0.75,
    "flax": 0.70,
    "rice": 0.85,  # 1 cup raw ~ 190g
    "salt": 1.20,
    # Nut Butters / Pastes
    "peanut butter": 1.08,  # 1 tbsp ~ 16g
    "almond butter": 1.08,
    "butter": 0.96,  # 1 cup ~ 227g (1 stick = 1/2 cup = 113g)
    "yogurt": 1.04,
    "greek yogurt": 1.06,
}

# Typical piece/discrete count weights in grams
COMMON_DISCRETE_WEIGHTS = {
    "egg": 50.0,
    "large egg": 50.0,
    "medium egg": 44.0,
    "small egg": 38.0,
    "egg white": 33.0,
    "egg yolk": 17.0,
    "banana": 118.0,
    "medium banana": 118.0,
    "large banana": 136.0,
    "small banana": 101.0,
    "apple": 182.0,
    "medium apple": 182.0,
    "large apple": 223.0,
    "small apple": 149.0,
    "orange": 131.0,
    "lemon": 58.0,
    "lime": 44.0,
    "avocado": 150.0,
    "garlic": 3.0,
    "clove": 3.0,
    "clove of garlic": 3.0,
    "cloves": 3.0,
    "onion": 150.0,
    "medium onion": 150.0,
    "small onion": 70.0,
    "large onion": 250.0,
    "carrot": 61.0,
    "medium carrot": 61.0,
    "slice": 30.0,  # e.g. bread/cheese default
    "slice of bread": 30.0,
    "tortilla": 45.0,
}


class UnitConverter:
    """
    Resolves natural language quantities and units into accurate gram weights.
    Prioritizes specific USDA portion data, followed by culinary density matrices
    and discrete unit models.
    """

    @classmethod
    def normalize_unit(cls, unit: Optional[str]) -> Optional[str]:
        """Normalize unit string abbreviations to canonical forms."""
        if not unit:
            return None

        u = unit.strip().lower().rstrip(".")
        # Mapping variations
        unit_map = {
            "tb": "tbsp",
            "tbs": "tbsp",
            "tbsps": "tbsp",
            "tablespoon": "tbsp",
            "tablespoons": "tbsp",
            "tsp": "tsp",
            "tsps": "tsp",
            "teaspoon": "tsp",
            "teaspoons": "tsp",
            "c": "cup",
            "cups": "cup",
            "oz": "oz",
            "ounce": "oz",
            "ounces": "oz",
            "fl oz": "fl oz",
            "fluid oz": "fl oz",
            "fluid ounce": "fl oz",
            "fluid ounces": "fl oz",
            "lb": "lb",
            "lbs": "lb",
            "pound": "lb",
            "pounds": "lb",
            "g": "g",
            "gm": "g",
            "gram": "g",
            "grams": "g",
            "kg": "kg",
            "kilogram": "kg",
            "kilograms": "kg",
            "ml": "ml",
            "milliliter": "ml",
            "milliliters": "ml",
            "l": "l",
            "liter": "l",
            "liters": "l",
            "pt": "pt",
            "pint": "pt",
            "pints": "pt",
            "qt": "qt",
            "quart": "qt",
            "quarts": "qt",
            "clove": "clove",
            "cloves": "clove",
            "slice": "slice",
            "slices": "slice",
            "pinch": "pinch",
            "pinches": "pinch",
            "dash": "dash",
            "can": "can",
            "cans": "can",
            "scoop": "scoop",
            "scoops": "scoop",
        }
        return unit_map.get(u, u)

    @classmethod
    def resolve_to_grams(
        cls,
        quantity: float,
        unit: Optional[str],
        food_name: str,
        usda_portions: Optional[list[dict]] = None,
    ) -> dict:
        """
        Convert a culinary quantity and unit into gram weight.

        Returns:
            dict containing:
                grams: float (the resolved weight in grams)
                source: str (e.g. 'direct_weight', 'usda_portion', 'density_lookup', 'discrete_count', 'default')
                matched_portion: Optional[str]
        """
        if quantity <= 0:
            return {"grams": 0.0, "source": "zero_quantity", "matched_portion": None}

        norm_unit = cls.normalize_unit(unit)
        clean_food = food_name.strip().lower()

        # 1. Direct mass unit (e.g. g, oz, lb, kg)
        if norm_unit and norm_unit in WEIGHT_UNITS_TO_GRAMS:
            grams = quantity * WEIGHT_UNITS_TO_GRAMS[norm_unit]
            return {
                "grams": round(grams, 2),
                "source": "direct_weight",
                "matched_portion": f"{quantity} {norm_unit}",
            }

        # 2. USDA Portions matching
        if usda_portions and norm_unit:
            portion_match = cls._match_usda_portion(quantity, norm_unit, usda_portions)
            if portion_match:
                return portion_match

        # 3. Discrete / Count units (e.g. 1 banana, 2 eggs, 3 cloves garlic, 2 slices)
        discrete_match = cls._match_discrete(quantity, norm_unit, clean_food)
        if discrete_match:
            return discrete_match

        # 4. Volumetric conversion with culinary density lookup
        if norm_unit and norm_unit in VOLUME_UNITS_TO_ML:
            volume_ml = quantity * VOLUME_UNITS_TO_ML[norm_unit]
            density = cls._find_density(clean_food)
            grams = volume_ml * density
            return {
                "grams": round(grams, 2),
                "source": "volumetric_density",
                "matched_portion": f"{quantity} {norm_unit} (density: {density}g/ml)",
            }

        # 5. Default fallback: If unit is missing or unrecognized, assume 100g base or unit grams
        fallback_grams = quantity * 100.0 if not norm_unit else quantity * 50.0
        return {
            "grams": round(fallback_grams, 2),
            "source": "fallback_estimation",
            "matched_portion": None,
        }

    @classmethod
    def _match_usda_portion(
        cls,
        quantity: float,
        unit: str,
        portions: list[dict],
    ) -> Optional[dict]:
        """Search USDA portions for matching unit description."""
        best_portion = None
        best_score = 0.0

        for p in portions:
            desc = (p.get("description") or "").lower()
            u_name = (p.get("unit") or "").lower()
            amt = float(p.get("amount") or 1.0)
            gram_weight = float(p.get("gram_weight") or 0.0)

            if gram_weight <= 0:
                continue

            # Check if unit is in portion description (e.g. "1 cup", "1 tbsp", "1 medium")
            score = 0.0
            if unit in desc.split() or unit == u_name:
                score = 1.0
            else:
                score = fuzz.token_set_ratio(unit, desc) / 100.0

            if score > 0.75 and score > best_score:
                best_score = score
                unit_weight = gram_weight / (amt if amt > 0 else 1.0)
                best_portion = {
                    "grams": round(quantity * unit_weight, 2),
                    "source": "usda_portion",
                    "matched_portion": desc,
                }

        return best_portion

    @classmethod
    def _match_discrete(
        cls, quantity: float, unit: Optional[str], food_name: str
    ) -> Optional[dict]:
        """Match discrete counts like 1 apple, 2 eggs, 3 cloves garlic."""
        # Check if unit itself is discrete (e.g. clove, slice)
        if unit in COMMON_DISCRETE_WEIGHTS:
            grams = quantity * COMMON_DISCRETE_WEIGHTS[unit]
            return {
                "grams": round(grams, 2),
                "source": "discrete_unit",
                "matched_portion": f"{quantity} {unit}",
            }

        # Check if food name has a standard count weight (e.g. egg, banana, apple)
        for key, weight in COMMON_DISCRETE_WEIGHTS.items():
            if key in food_name or fuzz.partial_ratio(key, food_name) >= 90:
                # If unit is 'medium', 'large', 'small', 'whole', or None, this is a count
                if not unit or unit in ["medium", "large", "small", "whole", "item", "piece", "pieces"]:
                    grams = quantity * weight
                    return {
                        "grams": round(grams, 2),
                        "source": "discrete_food_count",
                        "matched_portion": f"{quantity} {key}",
                    }

        return None

    @classmethod
    def _find_density(cls, food_name: str) -> float:
        """Find best matching culinary density factor (g/ml). Default is 1.0 (water)."""
        # Exact keyword check
        for key, density in CULINARY_DENSITIES.items():
            if key in food_name:
                return density

        # Fuzzy check
        best_match = None
        best_score = 0.0
        for key, density in CULINARY_DENSITIES.items():
            score = fuzz.partial_ratio(key, food_name)
            if score > 85 and score > best_score:
                best_score = score
                best_match = density

        return best_match if best_match is not None else 1.0
