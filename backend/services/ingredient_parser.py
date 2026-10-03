# backend/services/ingredient_parser.py
"""
Natural language ingredient parser.
Extracts quantity, unit, food name, and preparation notes from recipe text
using a fast deterministic regex/rule engine with Gemini structured LLM fallback.
"""

import logging
import re
import unicodedata
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Unicode fraction map
UNICODE_FRACTIONS = {
    "½": 0.5,
    "⅓": 1.0 / 3.0,
    "⅔": 2.0 / 3.0,
    "¼": 0.25,
    "¾": 0.75,
    "⅕": 0.2,
    "⅖": 0.4,
    "⅗": 0.6,
    "⅘": 0.8,
    "⅙": 1.0 / 6.0,
    "⅚": 5.0 / 6.0,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
}

# Common culinary preparation and state modifiers to extract
PREPARATION_TERMS = [
    "chopped",
    "diced",
    "minced",
    "sliced",
    "grated",
    "shredded",
    "peeled",
    "crushed",
    "melted",
    "softened",
    "toasted",
    "roasted",
    "ground",
    "cooked",
    "raw",
    "frozen",
    "fresh",
    "canned",
    "rinsed",
    "drained",
    "divided",
    "packed",
    "at room temperature",
    "to taste",
    "finely chopped",
    "roughly chopped",
    "thinly sliced",
    "sifted",
]

# Standard unit regex pattern
KNOWN_UNITS = [
    "tablespoons", "tablespoon", "tbsp", "tbs", "tb",
    "teaspoons", "teaspoon", "tsps", "tsp",
    "fluid ounces", "fluid ounce", "fl oz", "fl. oz.",
    "cups", "cup", "c.", "c",
    "pints", "pint", "pt",
    "quarts", "quart", "qt",
    "gallons", "gallon", "gal",
    "ounces", "ounce", "oz.", "oz",
    "pounds", "pound", "lbs.", "lbs", "lb.", "lb",
    "grams", "gram", "g.", "g",
    "milligrams", "milligram", "mg",
    "kilograms", "kilogram", "kg",
    "milliliters", "milliliter", "ml.", "ml",
    "liters", "liter", "l.", "l",
    "cloves", "clove",
    "slices", "slice",
    "pinches", "pinch",
    "dashes", "dash",
    "cans", "can",
    "scoops", "scoop",
    "sticks", "stick",
    "pieces", "piece", "pcs",
    "packages", "package", "pkg",
    "stalks", "stalk",
    "bunches", "bunch",
    "heads", "head",
    "sprigs", "sprig",
    "medium", "large", "small",
]

UNIT_REGEX = r"\b(" + "|".join(re.escape(u) for u in KNOWN_UNITS) + r")\b"


class ParsedIngredient(BaseModel):
    """Structured representation of a parsed culinary ingredient."""
    raw_text: str
    food_name: str
    quantity: float = 1.0
    unit: Optional[str] = None
    preparation: Optional[str] = None
    confidence: float = 1.0


class ParsedIngredientList(BaseModel):
    """List of parsed ingredients for LLM structured output."""
    ingredients: List[ParsedIngredient] = Field(default_factory=list)


class IngredientParser:
    """
    Parses messy culinary lines into structured ingredients.
    Uses regex/rule-based parsing first (< 1ms), falling back to Gemini
    structured output for ambiguous or complex phrases.
    """

    @classmethod
    def parse_quantity(cls, text: str) -> tuple[float, str]:
        """
        Extract numeric or fractional quantity from the start of a string.
        Returns: (quantity, remaining_text)
        """
        text = text.strip()

        # 1. Check for unicode fractions (e.g. "1 ½" or "½")
        for u_char, u_val in UNICODE_FRACTIONS.items():
            if u_char in text:
                # Handle "1 ½" or "1½"
                mixed_match = re.match(r"^(\d+)\s*" + re.escape(u_char), text)
                if mixed_match:
                    whole = float(mixed_match.group(1))
                    remaining = text[mixed_match.end():].strip()
                    return whole + u_val, remaining
                elif text.startswith(u_char):
                    remaining = text[len(u_char):].strip()
                    return u_val, remaining

        # 2. Check for mixed fractions: "2 1/2" or "1 3/4"
        mixed_match = re.match(r"^(\d+)\s+(\d+)/(\d+)", text)
        if mixed_match:
            whole = float(mixed_match.group(1))
            num = float(mixed_match.group(2))
            denom = float(mixed_match.group(3))
            remaining = text[mixed_match.end():].strip()
            return whole + (num / denom), remaining

        # 3. Check for simple fractions: "1/2", "3/4"
        frac_match = re.match(r"^(\d+)/(\d+)", text)
        if frac_match:
            num = float(frac_match.group(1))
            denom = float(frac_match.group(2))
            remaining = text[frac_match.end():].strip()
            return (num / denom), remaining

        # 4. Check for range: "2-3" or "2 to 3" (take average)
        range_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            remaining = text[range_match.end():].strip()
            return (low + high) / 2.0, remaining

        # 5. Check for decimal or whole number: "1.5", "2", "100"
        num_match = re.match(r"^(\d+(?:\.\d+)?)", text)
        if num_match:
            val = float(num_match.group(1))
            remaining = text[num_match.end():].strip()
            return val, remaining

        # Default: 1.0 (e.g. "salt", "banana")
        return 1.0, text

    @classmethod
    def parse_line(cls, line: str) -> ParsedIngredient:
        """
        Fast deterministic parser for a single ingredient line.
        """
        raw = line.strip()
        if not raw:
            return ParsedIngredient(raw_text="", food_name="", quantity=0.0, confidence=0.0)

        # Remove bullet points or numbered list indicators (e.g. "1. ", "- ", "* ")
        cleaned = re.sub(r"^\s*(?:[•\-–—*]|\d+[\.\)])\s*", "", raw).strip()
        if not cleaned:
            cleaned = raw

        # 1. Parse quantity
        quantity, after_qty = cls.parse_quantity(cleaned)

        # 2. Extract preparations and notes (in parentheses or comma separated)
        preparation = None
        # Check parenthetical notes: "1 cup milk (warm)"
        paren_match = re.search(r"\((.*?)\)", after_qty)
        if paren_match:
            preparation = paren_match.group(1).strip()
            after_qty = re.sub(r"\(.*?\)", "", after_qty).strip()

        # Check comma separated notes: "1 onion, diced"
        if "," in after_qty:
            parts = after_qty.split(",", 1)
            after_qty = parts[0].strip()
            extra_prep = parts[1].strip()
            preparation = f"{preparation}, {extra_prep}" if preparation else extra_prep

        # Check keyword preparation terms: "melted butter", "chopped parsley"
        for prep in PREPARATION_TERMS:
            pattern = r"\b" + re.escape(prep) + r"\b"
            if re.search(pattern, after_qty, re.IGNORECASE):
                preparation = f"{preparation}, {prep}" if preparation else prep
                after_qty = re.sub(pattern, "", after_qty, flags=re.IGNORECASE).strip()

        # 3. Extract unit
        unit = None
        unit_match = re.match(UNIT_REGEX, after_qty, re.IGNORECASE)
        if unit_match:
            unit = unit_match.group(1).lower().rstrip(".")
            food_part = after_qty[unit_match.end():].strip()
        else:
            food_part = after_qty.strip()

        # 4. Clean food name (remove leading 'of', extra spaces, punctuation)
        food_part = re.sub(r"^(?:of|for)\s+", "", food_part, flags=re.IGNORECASE).strip()
        food_part = re.sub(r"\s+", " ", food_part).strip(" ,.-")

        confidence = 0.95 if food_part and unit else (0.80 if food_part else 0.40)

        return ParsedIngredient(
            raw_text=raw,
            food_name=food_part or raw,
            quantity=round(quantity, 3),
            unit=unit,
            preparation=preparation,
            confidence=confidence,
        )

    @classmethod
    def parse_recipe_text(cls, text: str) -> List[ParsedIngredient]:
        """
        Parse multi-line recipe text into a list of structured ingredients.
        Splits by newlines, semi-colons, or numbered lists.
        """
        if not text or not text.strip():
            return []

        # Split into distinct lines
        raw_lines = re.split(r"[\n;]+", text)
        results: List[ParsedIngredient] = []

        for line in raw_lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 2:
                continue
            # Skip pure headers like "Ingredients:" or "For the dressing:"
            if line_str.lower().endswith(":") and not re.search(r"\d", line_str):
                continue

            parsed = cls.parse_line(line_str)
            if parsed.food_name:
                results.append(parsed)

        return results

    @classmethod
    async def parse_with_llm_fallback(
        cls,
        text: str,
        threshold_confidence: float = 0.70,
    ) -> List[ParsedIngredient]:
        """
        Parse with fast regex first. If any ingredient has low confidence or the text
        is freeform narrative, invoke Gemini structured output.
        """
        deterministic_results = cls.parse_recipe_text(text)

        # Check if all items parsed with high confidence
        all_confident = deterministic_results and all(
            ing.confidence >= threshold_confidence and len(ing.food_name) > 1
            for ing in deterministic_results
        )

        if all_confident:
            return deterministic_results

        # Fallback to Gemini 2.0 Flash structured output
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from backend.config import settings

            if not settings.gemini_api_key:
                return deterministic_results

            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=0,
            )
            structured_llm = llm.with_structured_output(ParsedIngredientList)

            prompt = (
                "Extract all food ingredients from this recipe text. "
                "For each ingredient, identify the quantity (as a decimal float), "
                "culinary unit (e.g. cup, tbsp, tsp, g, oz, clove, medium, or null if count), "
                "clean food name (without units or prep), and any preparation notes.\n\n"
                f"Recipe text:\n{text}"
            )

            result: ParsedIngredientList = await structured_llm.ainvoke(prompt)
            if result and result.ingredients:
                return result.ingredients

        except Exception as e:
            logger.warning(f"LLM fallback parsing error ({e}), returning deterministic results.")

        return deterministic_results
