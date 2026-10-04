# backend/services/vision.py
"""Multimodal Vision Ingestion Pipeline for Meal and Label Analysis."""

import base64
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from PIL import Image

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from backend.config import settings
from backend.services.nutrition import NutritionService
from backend.services.labels import LabelService, LabelLayoutConfig


# ============================================
# Pydantic Extraction Schemas
# ============================================

class DetectedFoodItem(BaseModel):
    name: str = Field(description="Name of the food item or ingredient (e.g. 'grilled salmon', 'brown rice')")
    quantity: float = Field(default=1.0, description="Estimated quantity or numeric portion")
    unit: str = Field(default="serving", description="Unit of measurement (e.g. 'g', 'oz', 'cup', 'fillet', 'slice', 'serving')")
    confidence: Optional[float] = Field(default=0.85, description="Confidence score between 0.0 and 1.0")


class MealVisionExtraction(BaseModel):
    meal_name: str = Field(description="Descriptive name of the dish or meal")
    description: str = Field(description="Visual observation of dish composition, cooking style, and visible ingredients")
    items: List[DetectedFoodItem] = Field(description="List of detected food items and their estimated portions")
    dietary_flags: List[str] = Field(default_factory=list, description="Dietary tags e.g. 'high-protein', 'low-carb', 'keto', 'vegan', 'gluten-free'")
    estimated_prep_notes: Optional[str] = Field(default="", description="Observations on preparation (e.g. fried, steamed, fresh)")


class PhysicalLabelExtraction(BaseModel):
    food_name: str = Field(default="Packaged Food", description="Brand or product name identified on the nutrition label")
    serving_size: str = Field(default="100g", description="Serving size declaration, e.g. '1 cup (240ml)', '2 cookies (30g)'")
    servings_per_container: float = Field(default=1.0, description="Number of servings per container")
    calories: float = Field(default=0.0, description="Calories per serving")
    fat: float = Field(default=0.0, description="Total Fat in grams")
    sat_fat: float = Field(default=0.0, description="Saturated Fat in grams")
    trans_fat: float = Field(default=0.0, description="Trans Fat in grams")
    cholesterol: float = Field(default=0.0, description="Cholesterol in milligrams")
    sodium: float = Field(default=0.0, description="Sodium in milligrams")
    carbs: float = Field(default=0.0, description="Total Carbohydrate in grams")
    fiber: float = Field(default=0.0, description="Dietary Fiber in grams")
    sugars: float = Field(default=0.0, description="Total Sugars in grams")
    added_sugars: float = Field(default=0.0, description="Added Sugars in grams")
    protein: float = Field(default=0.0, description="Protein in grams")
    vit_d: float = Field(default=0.0, description="Vitamin D in micrograms")
    calcium: float = Field(default=0.0, description="Calcium in milligrams")
    iron: float = Field(default=0.0, description="Iron in milligrams")
    potassium: float = Field(default=0.0, description="Potassium in milligrams")


# ============================================
# Vision Service
# ============================================

class VisionService:
    """
    Multimodal Vision Ingestion Service.
    Integrates Gemini Vision with USDA Entity Resolution and FDA Label Reconstruction.
    """

    def __init__(
        self,
        nutrition_service: Optional[NutritionService] = None,
        label_service: Optional[LabelService] = None,
        labels_dir: Optional[Path] = None,
    ):
        self._nutrition_service = nutrition_service or NutritionService()
        self._label_service = label_service or LabelService()
        self._labels_dir = labels_dir or (Path(__file__).parent.parent / "data" / "labels")
        self._labels_dir.mkdir(parents=True, exist_ok=True)

    def _get_vision_llm(self):
        """Instantiate Google Gemini Vision Chat Model."""
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.2,
        )

    def prepare_image(self, image_bytes: bytes, max_dimension: int = 1536) -> tuple[bytes, str]:
        """Validate and optimize image size and dimensions."""
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                format_name = (img.format or "jpeg").lower()
                mime_type = "image/jpeg" if format_name in ["jpg", "jpeg"] else f"image/{format_name}"

                w, h = img.size
                if max(w, h) > max_dimension:
                    scale = max_dimension / max(w, h)
                    new_size = (int(w * scale), int(h * scale))
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    if resized_img.mode in ("RGBA", "P"):
                        resized_img = resized_img.convert("RGB")
                    resized_img.save(buf, format="JPEG", quality=85)
                    return buf.getvalue(), "image/jpeg"

                return image_bytes, mime_type
        except Exception as e:
            raise ValueError(f"Invalid or unsupported image data: {e}")

    def _encode_to_data_url(self, image_bytes: bytes, mime_type: str) -> str:
        """Encode image bytes to base64 Data URL."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

    async def analyze_meal_async(
        self,
        image_bytes: bytes,
        user_notes: str = "",
    ) -> Dict[str, Any]:
        """
        Analyze photo of a meal or plate:
        1. Extract visible food ingredients and portions using Gemini Vision.
        2. Resolve items against USDA FoodData Central via NutritionService.
        3. Return verified macro totals and structured ingredient breakdown.
        """
        processed_bytes, mime_type = self.prepare_image(image_bytes)
        data_url = self._encode_to_data_url(processed_bytes, mime_type)

        llm = self._get_vision_llm()
        structured_model = llm.with_structured_output(MealVisionExtraction)

        prompt_text = (
            "You are an expert nutritionist and culinary analyst examining an image of a meal.\n"
            "Identify each food component, estimating its portion size in culinary units (e.g. grams, cups, tbsp, ounces, slices, or pieces).\n"
            "Be precise with common ingredients (proteins, grains, vegetables, dressings, fats).\n"
        )
        if user_notes:
            prompt_text += f"Additional context provided by user: '{user_notes}'.\n"

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        )

        extraction: MealVisionExtraction = await structured_model.ainvoke([message])

        # Step 2: Cross-validate and resolve with USDA FoodData Central
        ingredient_items = [
            {
                "name": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "raw_text": f"{item.quantity} {item.unit} {item.name}".strip(),
            }
            for item in extraction.items
        ]

        recipe_nutrition = await self._nutrition_service.calculate_recipe_async(ingredient_items)

        return {
            "meal_name": extraction.meal_name,
            "description": extraction.description,
            "dietary_flags": extraction.dietary_flags,
            "estimated_prep_notes": extraction.estimated_prep_notes,
            "detected_items": [item.model_dump() for item in extraction.items],
            "recipe_totals": recipe_nutrition.get("recipe_totals", {}),
            "ingredients": recipe_nutrition.get("ingredients", []),
            "exportable": recipe_nutrition.get("exportable", {}),
            "status": "success",
        }

    async def extract_and_reconstruct_label_async(
        self,
        image_bytes: bytes,
    ) -> Dict[str, Any]:
        """
        Analyze photo of a physical Nutrition Facts panel:
        1. OCR and extract exact nutrients using Gemini Vision.
        2. Reconstruct a clean digital FDA-compliant label image using LabelService.
        3. Return structured nutrients and the image path.
        """
        processed_bytes, mime_type = self.prepare_image(image_bytes)
        data_url = self._encode_to_data_url(processed_bytes, mime_type)

        llm = self._get_vision_llm()
        structured_model = llm.with_structured_output(PhysicalLabelExtraction)

        prompt_text = (
            "You are an expert FDA regulatory specialist reviewing a physical Nutrition Facts label.\n"
            "Extract all printed values with precision (Serving size, Servings per container, Calories, "
            "Total Fat, Saturated Fat, Trans Fat, Cholesterol, Sodium, Total Carbs, Fiber, Sugars, "
            "Added Sugars, Protein, Vitamin D, Calcium, Iron, Potassium).\n"
            "If a nutrient is listed as 0g or less than 1g, record the numeric value accurately."
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        )

        extraction: PhysicalLabelExtraction = await structured_model.ainvoke([message])

        # Step 2: Render digital FDA label
        nutrition_dict = extraction.model_dump()
        layout = LabelLayoutConfig(
            serving_size=extraction.serving_size,
            servings_per_container=int(round(extraction.servings_per_container)),
            title="Nutrition Facts",
        )

        rendered_png = self._label_service.generate_image(
            nutrition=nutrition_dict,
            food_name=extraction.food_name,
            layout=layout,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in extraction.food_name)[:30]
        filename = f"reconstructed_{safe_name}_{timestamp}.png"
        filepath = self._labels_dir / filename
        filepath.write_bytes(rendered_png)

        return {
            "food_name": extraction.food_name,
            "serving_size": extraction.serving_size,
            "servings_per_container": extraction.servings_per_container,
            "nutrition": nutrition_dict,
            "image_url": f"/labels/{filename}",
            "filename": filename,
            "status": "reconstructed",
        }
