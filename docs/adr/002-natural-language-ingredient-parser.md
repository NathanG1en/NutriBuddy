# ADR 002: Natural Language Ingredient Parsing & Portion Normalization Engine

## Status
**Accepted & Implemented**

## Context
In NutriBuddy's legacy implementation, nutrition calculation strictly required manual gram inputs (e.g. `[{"name": "flour", "grams": 200}]`). Real users and recipes operate in natural culinary measurements:
* Fractions and units: *"2 1/2 cups rolled oats"*, *"1/2 cup whole milk"*, *"2 tbsp peanut butter"*
* Counts and discrete produce: *"1 medium banana"*, *"2 large eggs"*, *"3 cloves garlic"*
* Imperial vs Metric: *"4 oz chicken"*, *"1 lb beef"*, *"250g flour"*
* Preparation phrases: *"onion, finely diced"*, *"butter (melted)"*

Without a parser and unit resolution engine, users were forced to mentally convert recipes to grams before entering them, creating heavy friction in both the UI and AI conversational chat.

## Decisions

### 1. Two-Tier Parsing Architecture (`IngredientParser`)
* **Tier 1 (Sub-millisecond Deterministic Regex Engine)**:
  * Parses numeric fractions, mixed fractions (`2 1/2`), unicode fractions (`½`, `¾`), ranges (`2-3`), and decimals.
  * Normalizes culinary unit variants and abbreviations (`tbsp`, `tbs`, `tablespoon` -> `tbsp`).
  * Strips preparations and parentheticals (`diced`, `warm`, `chopped`, `extra virgin`) to extract a clean food query for USDA search.
* **Tier 2 (Gemini 2.0 Flash Structured Output Fallback)**:
  * For ambiguous, unstructured prose or multi-item sentences, invokes Gemini with a Pydantic `ParsedIngredientList` schema.

### 2. Multi-Stage Unit Conversion Matrix (`UnitConverter`)
* **Stage 1 (Direct Mass)**: Exact weight conversions (`g`, `oz`, `lb`, `kg`, `mg`).
* **Stage 2 (USDA Portion Resolution)**: Ingests USDA FoodData `foodPortions` metadata to resolve food-specific portion weights (e.g. `1 cup oats = 81g`, `1 cup milk = 245g`).
* **Stage 3 (Discrete Food Counts)**: Heuristic weights for common produce and items (e.g. `large egg = 50g`, `medium banana = 118g`, `garlic clove = 3g`).
* **Stage 4 (Volumetric Culinary Density)**: Density table (g/ml) for liquids, flours, sugars, nut butters, and oils.

### 3. Service & Tool Integration
* Upgraded `NutritionService.calculate_recipe_async` to accept arbitrary strings (`"2 cups oats"`), structured objects (`{"name": "oats", "quantity": 2, "unit": "cup"}`), or legacy gram dictionaries.
* Added `/api/recipe/parse` endpoint to FastAPI to support real-time frontend recipe parsing.
* Added `parse_recipe_text` tool and updated `calculate_recipe_nutrition` tool in LangGraph agent.

## Consequences & Verification
* **User Experience**: Users and LLMs can pass raw recipe text directly.
* **Accuracy**: Resolves exact USDA portion weights first before falling back to culinary density tables.
* **Test Coverage**: 9 dedicated unit tests added in `tests/test_ingredient_parser.py` and `tests/test_unit_converter.py`; all 22 test suite cases pass.
