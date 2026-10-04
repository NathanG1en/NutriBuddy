# ADR 004: Multimodal Vision Ingestion Pipeline for Meals & Physical Labels

* **Status**: Implemented / Accepted
* **Date**: October 2026
* **Deciders**: AI & Data Engineering Pair
* **Related Track**: Track 4: Multimodal Vision Ingestion Pipeline ([Backend Roadmap](../roadmap/backend-roadmap.md#%EF%B8%8F-track-4-multimodal-vision-ingestion-pipeline))

---

## Context

Tracking nutrition and building FDA-style nutrition labels from real-world meals or packaged foods traditionally required tedious manual data entry:
1. **Manual Meal Logging**: Users had to identify each ingredient on a plate, look up portion sizes, and manually enter weights or volume units.
2. **Packaged Label Transcriptions**: Physical nutrition labels on packaged foods contain dense numerical grids (Calories, Saturated Fat, Sodium, Daily Values, Vitamins). Manually transcribing these values into a software system is slow, error-prone, and frustrating.
3. **Disconnected Visual Capabilities**: Despite modern multimodal foundation models (Gemini 2.0 / 3.8 Flash Vision), NutriBuddy lacked an automated ingestion pipeline that could ingest an arbitrary photograph (meal or physical label) and connect it directly to verified USDA nutrition data and digital label generation.

---

## Decisions

### 1. Two-Tier Multimodal Architecture (`VisionService`)
We created [backend/services/vision.py](file:///Users/nathanglen/NutriBuddy/backend/services/vision.py) providing two specialized vision pipelines:

#### A. Plate & Meal Vision Analysis (`analyze_meal_async`)
* **Visual Ingestion**: Ingests meal photos (JPEG, PNG, WebP), auto-resizes large inputs via Pillow (`LANCZOS`, max dimension 1536px), and converts to Base64 Data URLs.
* **Structured Extraction**: Prompts Google Gemini with `with_structured_output(MealVisionExtraction)` to extract:
  * `meal_name`: Descriptive dish title
  * `description`: Visual composition and culinary style
  * `items`: List of detected ingredients, numeric quantities, and natural culinary units
  * `dietary_flags`: Inferred tags (`high-protein`, `keto`, `gluten-free`, `vegan`, etc.)
* **USDA Cross-Validation**: Immediately passes the detected ingredients to `NutritionService.calculate_recipe_async` to cross-validate visual portion estimates against USDA FoodData Central and compute verified macro totals and per-ingredient breakdowns.

#### B. Physical Label OCR & Digital Reconstruction (`extract_and_reconstruct_label_async`)
* **Precision OCR**: Prompts Google Gemini with `with_structured_output(PhysicalLabelExtraction)` to extract all printed FDA nutrient values (Calories, Fat, Saturated/Trans Fat, Cholesterol, Sodium, Carbs, Fiber, Sugars, Added Sugars, Protein, Vit D, Calcium, Iron, Potassium) alongside serving declarations.
* **Digital Reconstruction**: Automatically hydrates `LabelService.generate_image` to render a pixel-accurate, digital FDA Nutrition Facts label image (`/labels/reconstructed_<name>_<timestamp>.png`).

### 2. Dedicated FastAPI Endpoints
Added [backend/api/routes/vision.py](file:///Users/nathanglen/NutriBuddy/backend/api/routes/vision.py):
* `POST /api/vision/meal`: Multipart file upload for plate/meal photo analysis and USDA nutritional verification.
* `POST /api/vision/label`: Multipart file upload for physical label OCR and automatic digital label reconstruction.

### 3. Agent Tool Integration
Added `analyze_food_image` tool in [backend/agent/tools.py](file:///Users/nathanglen/NutriBuddy/backend/agent/tools.py) returning typed `meal_vision` artifacts so that the LangGraph conversational agent can directly inspect and reason about user-provided food images during chat.

---

## Consequences & Impact

### Positive
* **Frictionless Ingestion**: Users can photograph a plate of food or a packaged label and immediately receive verified USDA nutritional data or a reconstructed digital label.
* **Cross-Validated Accuracy**: Visual estimates are grounded in USDA FoodData Central rather than relying solely on LLM hallucinations.
* **Deterministic Structured Data**: Outputs use strict Pydantic schemas, eliminating regex parsing brittleness.
* **Non-Blocking Performance**: Fully integrated with FastAPI's async execution model.
