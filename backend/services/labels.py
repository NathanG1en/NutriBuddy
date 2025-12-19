# backend/services/labels.py
"""Nutrition label generation service - configurable and extensible."""

import io
from dataclasses import dataclass, field
from typing import Protocol, Callable
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


# ============================================
# Configuration / Schema
# ============================================

@dataclass
class NutrientConfig:
    """Defines how a nutrient should be displayed."""
    key: str  # Key in nutrition data (e.g., "protein")
    label: str  # Display name (e.g., "Protein")
    unit: str  # Unit (e.g., "g", "mg", "mcg")
    daily_value: float | None = None  # DV for % calculation (None = don't show %)
    indent: bool = False  # Indent as sub-nutrient
    bold: bool = False  # Bold text


@dataclass
class LabelLayoutConfig:
    """Configuration for label appearance."""
    width: int = 400
    height: int = 600
    padding: int = 15
    background_color: str = "white"
    text_color: str = "black"
    line_color: str = "black"
    serving_size: str = "100g"
    servings_per_container: int = 1
    show_daily_values: bool = True
    title: str = "Nutrition Facts"


# Default FDA nutrient schema
DEFAULT_NUTRIENTS: list[NutrientConfig] = [
    NutrientConfig("fat", "Total Fat", "g", daily_value=78, bold=True),
    NutrientConfig("sat_fat", "Saturated Fat", "g", daily_value=20, indent=True),
    NutrientConfig("trans_fat", "Trans Fat", "g", indent=True),
    NutrientConfig("cholesterol", "Cholesterol", "mg", daily_value=300, bold=True),
    NutrientConfig("sodium", "Sodium", "mg", daily_value=2300, bold=True),
    NutrientConfig("carbs", "Total Carbohydrate", "g", daily_value=275, bold=True),
    NutrientConfig("fiber", "Dietary Fiber", "g", daily_value=28, indent=True),
    NutrientConfig("sugars", "Total Sugars", "g", indent=True),
    NutrientConfig("added_sugars", "Incl. Added Sugars", "g", daily_value=50, indent=True),
    NutrientConfig("protein", "Protein", "g", daily_value=50, bold=True),
]

DEFAULT_MICRONUTRIENTS: list[NutrientConfig] = [
    NutrientConfig("vit_d", "Vitamin D", "mcg", daily_value=20),
    NutrientConfig("calcium", "Calcium", "mg", daily_value=1300),
    NutrientConfig("iron", "Iron", "mg", daily_value=18),
    NutrientConfig("potassium", "Potassium", "mg", daily_value=4700),
]


# ============================================
# Font Loader (cross-platform)
# ============================================

class FontLoader:
    """Cross-platform font loading with fallback."""

    FONT_PATHS = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]

    @classmethod
    def load(cls, size: int = 16) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for path in cls.FONT_PATHS:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()


# ============================================
# Renderers (Strategy Pattern)
# ============================================

# class LabelRenderer(Protocol):
#     """Protocol for label renderers - allows different output formats."""
#
#     def render(
#             self,
#             nutrition: dict,
#             food_name: str,
#             layout: LabelLayoutConfig,
#             nutrients: list[NutrientConfig],
#             micronutrients: list[NutrientConfig],
#     ) -> bytes | str:
#         ...


class TextLabelRenderer:
    """Renders labels as formatted text."""

    def render(
            self,
            nutrition: dict,
            food_name: str,
            layout: LabelLayoutConfig,
            nutrients: list[NutrientConfig],
            micronutrients: list[NutrientConfig],
    ) -> str:
        lines = [
            "═" * 40,
            f"  {layout.title}",
            f"  {food_name}",
            "═" * 40,
            "",
            f"Serving Size: {layout.serving_size}",
            f"Servings Per Container: {layout.servings_per_container}",
            "─" * 40,
            "",
            f"Calories ............. {nutrition.get('calories', 0):.0f}",
            "",
        ]

        # Nutrients
        for n in nutrients:
            value = nutrition.get(n.key, 0)
            indent = "  " if n.indent else ""
            dv_str = ""
            if layout.show_daily_values and n.daily_value:
                dv_pct = (value / n.daily_value) * 100
                dv_str = f"  {dv_pct:.0f}%"

            line = f"{indent}{n.label} {'.' * (20 - len(n.label) - len(indent))} {value:.1f}{n.unit}{dv_str}"
            lines.append(line)

        lines.append("")
        lines.append("─" * 40)

        # Micronutrients
        for n in micronutrients:
            value = nutrition.get(n.key, 0)
            dv_str = ""
            if layout.show_daily_values and n.daily_value:
                dv_pct = (value / n.daily_value) * 100
                dv_str = f"  {dv_pct:.0f}%"
            lines.append(f"{n.label}: {value:.1f}{n.unit}{dv_str}")

        lines.append("═" * 40)

        return "\n".join(lines)


class ImageLabelRenderer:
    """Renders labels as PNG images."""

    def render(
            self,
            nutrition: dict,
            food_name: str,
            layout: LabelLayoutConfig,
            nutrients: list[NutrientConfig],
            micronutrients: list[NutrientConfig],
    ) -> bytes:
        img = Image.new("RGB", (layout.width, layout.height), layout.background_color)
        draw = ImageDraw.Draw(img)

        font = FontLoader.load(16)
        font_bold = FontLoader.load(18)
        font_title = FontLoader.load(28)
        font_small = FontLoader.load(12)

        y = layout.padding
        pad = layout.padding
        w = layout.width

        # Border
        draw.rectangle([3, 3, w - 3, layout.height - 3], outline=layout.line_color, width=2)

        # Title
        draw.text((pad, y), layout.title, font=font_title, fill=layout.text_color)
        y += 35

        # Food name
        draw.text((pad, y), food_name[:40], font=font, fill=layout.text_color)
        y += 22

        # Thick separator
        draw.rectangle([pad, y, w - pad, y + 8], fill=layout.line_color)
        y += 15

        # Serving info
        draw.text((pad, y), f"Serving Size: {layout.serving_size}", font=font, fill=layout.text_color)
        y += 22

        # Calories section
        draw.rectangle([pad, y, w - pad, y + 3], fill=layout.line_color)
        y += 8
        draw.text((pad, y), "Calories", font=font_bold, fill=layout.text_color)
        cal = nutrition.get("calories", 0)
        draw.text((w - pad - 60, y), f"{cal:.0f}", font=font_bold, fill=layout.text_color)
        y += 28

        # % DV header
        draw.rectangle([pad, y, w - pad, y + 2], fill=layout.line_color)
        y += 6
        if layout.show_daily_values:
            draw.text((w - pad - 80, y), "% Daily Value*", font=font_small, fill=layout.text_color)
            y += 18

        # Nutrients
        for n in nutrients:
            value = nutrition.get(n.key, 0)
            indent = 20 if n.indent else 0
            f = font_bold if n.bold else font

            label_text = f"{n.label} {value:.1f}{n.unit}"
            draw.text((pad + indent, y), label_text, font=f, fill=layout.text_color)

            if layout.show_daily_values and n.daily_value:
                dv_pct = (value / n.daily_value) * 100
                draw.text((w - pad - 40, y), f"{dv_pct:.0f}%", font=font, fill=layout.text_color)

            y += 22

        # Micronutrient section
        draw.rectangle([pad, y, w - pad, y + 6], fill=layout.line_color)
        y += 12

        for n in micronutrients:
            value = nutrition.get(n.key, 0)
            draw.text((pad, y), f"{n.label} {value:.1f}{n.unit}", font=font, fill=layout.text_color)

            if layout.show_daily_values and n.daily_value:
                dv_pct = (value / n.daily_value) * 100
                draw.text((w - pad - 40, y), f"{dv_pct:.0f}%", font=font, fill=layout.text_color)

            y += 20

        # Footer
        y += 10
        footer = "* Percent Daily Values based on a 2,000 calorie diet."
        draw.text((pad, y), footer, font=font_small, fill=layout.text_color)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


# ============================================
# Label Service (Facade)
# ============================================

class LabelService:
    """
    Generates nutrition labels with configurable layout and nutrients.

    Follows Open/Closed Principle:
    - Open for extension: Pass custom layouts, nutrients, or renderers
    - Closed for modification: Core logic doesn't change
    """

    def __init__(
            self,
            layout: LabelLayoutConfig | None = None,
            nutrients: list[NutrientConfig] | None = None,
            micronutrients: list[NutrientConfig] | None = None,
            text_renderer: TextLabelRenderer | None = None,
            image_renderer: ImageLabelRenderer | None = None,
    ):
        self._layout = layout or LabelLayoutConfig()
        self._nutrients = nutrients or DEFAULT_NUTRIENTS
        self._micronutrients = micronutrients or DEFAULT_MICRONUTRIENTS
        self._text_renderer = text_renderer or TextLabelRenderer()
        self._image_renderer = image_renderer or ImageLabelRenderer()

    def format_text(
            self,
            nutrition: dict,
            food_name: str = "Food Item",
            layout: LabelLayoutConfig | None = None,
    ) -> str:
        """Generate a text-based nutrition label."""
        return self._text_renderer.render(
            nutrition=nutrition,
            food_name=food_name,
            layout=layout or self._layout,
            nutrients=self._nutrients,
            micronutrients=self._micronutrients,
        )

    def generate_image(
            self,
            nutrition: dict,
            food_name: str = "Food Item",
            layout: LabelLayoutConfig | None = None,
    ) -> bytes:
        """Generate FDA-style nutrition label as PNG bytes."""
        return self._image_renderer.render(
            nutrition=nutrition,
            food_name=food_name,
            layout=layout or self._layout,
            nutrients=self._nutrients,
            micronutrients=self._micronutrients,
        )

    # ============================================
    # Factory methods for common configurations
    # ============================================

    @classmethod
    def with_custom_serving(cls, serving_size: str, servings: int = 1) -> "LabelService":
        """Create a service with custom serving size."""
        layout = LabelLayoutConfig(
            serving_size=serving_size,
            servings_per_container=servings,
        )
        return cls(layout=layout)

    @classmethod
    def compact(cls) -> "LabelService":
        """Create a compact label (smaller dimensions, no DV%)."""
        layout = LabelLayoutConfig(
            width=300,
            height=400,
            show_daily_values=False,
        )
        return cls(layout=layout)