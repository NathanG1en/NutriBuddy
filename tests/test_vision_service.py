import io
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from PIL import Image
from fastapi.testclient import TestClient

from backend.services.vision import (
    VisionService,
    DetectedFoodItem,
    MealVisionExtraction,
    PhysicalLabelExtraction,
)
from backend.agent.tools import analyze_food_image
from backend.api.main import app
from backend.dependencies import get_vision_service
from backend.api.security import get_current_user


def _create_test_image(width: int = 100, height: int = 100, format: str = "PNG") -> bytes:
    img = Image.new("RGB", (width, height), color="green")
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_prepare_image_valid():
    service = VisionService()
    img_bytes = _create_test_image(200, 200)
    processed, mime_type = service.prepare_image(img_bytes)
    assert len(processed) > 0
    assert mime_type == "image/png"


def test_prepare_image_resize_large():
    service = VisionService()
    img_bytes = _create_test_image(2000, 1000)
    processed, mime_type = service.prepare_image(img_bytes, max_dimension=1000)
    with Image.open(io.BytesIO(processed)) as res:
        w, h = res.size
        assert max(w, h) <= 1000
    assert mime_type == "image/jpeg"


def test_prepare_image_invalid():
    service = VisionService()
    with pytest.raises(ValueError, match="Invalid or unsupported image data"):
        service.prepare_image(b"not-an-image-data")


@pytest.mark.asyncio
async def test_analyze_meal_async():
    mock_nutrition_svc = MagicMock()
    mock_nutrition_svc.calculate_recipe_async = AsyncMock(return_value={
        "recipe_totals": {"calories": 420.0, "protein": 35.0, "carbs": 15.0, "fat": 22.0},
        "ingredients": [{"name": "salmon fillet", "calories": 300.0, "grams": 150.0}],
        "exportable": {"ingredients": [{"name": "salmon", "grams": 150.0}], "totals": {"calories": 420.0}},
    })

    service = VisionService(nutrition_service=mock_nutrition_svc)

    mock_extraction = MealVisionExtraction(
        meal_name="Grilled Salmon with Asparagus",
        description="Freshly grilled salmon steak accompanied by steamed green asparagus spears.",
        items=[
            DetectedFoodItem(name="salmon fillet", quantity=150.0, unit="g", confidence=0.95),
            DetectedFoodItem(name="asparagus", quantity=1.0, unit="cup", confidence=0.90),
        ],
        dietary_flags=["high-protein", "keto", "gluten-free"],
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_extraction)

    with patch.object(service, "_get_vision_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output.return_value = mock_structured_llm
        mock_get_llm.return_value = mock_llm_instance

        img_bytes = _create_test_image()
        result = await service.analyze_meal_async(img_bytes, user_notes="light oil")

        assert result["meal_name"] == "Grilled Salmon with Asparagus"
        assert len(result["detected_items"]) == 2
        assert "high-protein" in result["dietary_flags"]
        assert result["recipe_totals"]["calories"] == 420.0
        assert result["status"] == "success"
        mock_nutrition_svc.calculate_recipe_async.assert_called_once()


@pytest.mark.asyncio
async def test_extract_and_reconstruct_label_async(tmp_path):
    mock_label_svc = MagicMock()
    mock_label_svc.generate_image.return_value = b"reconstructed-label-png"

    service = VisionService(label_service=mock_label_svc, labels_dir=tmp_path)

    mock_extraction = PhysicalLabelExtraction(
        food_name="Protein Granola Bar",
        serving_size="1 bar (45g)",
        servings_per_container=1.0,
        calories=190.0,
        fat=6.0,
        sat_fat=1.0,
        trans_fat=0.0,
        cholesterol=0.0,
        sodium=140.0,
        carbs=22.0,
        fiber=4.0,
        sugars=8.0,
        added_sugars=6.0,
        protein=12.0,
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_extraction)

    with patch.object(service, "_get_vision_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output.return_value = mock_structured_llm
        mock_get_llm.return_value = mock_llm_instance

        img_bytes = _create_test_image()
        result = await service.extract_and_reconstruct_label_async(img_bytes)

        assert result["food_name"] == "Protein Granola Bar"
        assert result["nutrition"]["calories"] == 190.0
        assert result["status"] == "reconstructed"
        assert result["image_url"].startswith("/labels/reconstructed_")
        assert (tmp_path / result["filename"]).exists()


def test_analyze_food_image_tool(tmp_path):
    test_img = tmp_path / "sample_dish.jpg"
    test_img.write_bytes(_create_test_image())

    mock_vision_svc = MagicMock()
    mock_vision_svc.analyze_meal_async = AsyncMock(return_value={
        "meal_name": "Avocado Toast",
        "description": "Sourdough toast topped with mashed avocado.",
        "detected_items": [{"name": "avocado", "quantity": 1, "unit": "medium"}],
        "recipe_totals": {"calories": 250.0},
        "ingredients": [{"name": "avocado", "calories": 250.0}],
    })

    with patch("backend.dependencies.get_vision_service", return_value=mock_vision_svc):
        tool_call = {
            "name": "analyze_food_image",
            "args": {"image_path_or_url": str(test_img), "notes": "sprinkled with chili flakes"},
            "id": "call_vision_1",
            "type": "tool_call",
        }
        tool_msg = analyze_food_image.invoke(tool_call)

        assert tool_msg.artifact["type"] == "meal_vision"
        assert tool_msg.artifact["meal_name"] == "Avocado Toast"
        assert tool_msg.artifact["recipe_totals"]["calories"] == 250.0


def test_vision_api_routes(tmp_path):
    mock_vision_svc = MagicMock()
    mock_vision_svc.analyze_meal_async = AsyncMock(return_value={
        "meal_name": "Berry Smoothie",
        "description": "Blended berries and yogurt.",
        "detected_items": [{"name": "blueberries", "quantity": 1, "unit": "cup"}],
        "recipe_totals": {"calories": 180.0},
        "ingredients": [],
        "status": "success",
    })
    mock_vision_svc.extract_and_reconstruct_label_async = AsyncMock(return_value={
        "food_name": "Greek Yogurt",
        "serving_size": "170g",
        "servings_per_container": 1,
        "nutrition": {"calories": 100.0},
        "image_url": "/labels/reconstructed_Greek_Yogurt.png",
        "filename": "reconstructed_Greek_Yogurt.png",
        "status": "reconstructed",
    })

    app.dependency_overrides[get_vision_service] = lambda: mock_vision_svc
    app.dependency_overrides[get_current_user] = lambda: {"uid": "test_user"}

    client = TestClient(app)

    # 1. Test POST /api/vision/meal
    img_data = _create_test_image()
    files = {"file": ("meal.png", img_data, "image/png")}
    response = client.post("/api/vision/meal", files=files, data={"notes": "healthy"})
    assert response.status_code == 200
    data = response.json()
    assert data["meal_name"] == "Berry Smoothie"
    assert data["recipe_totals"]["calories"] == 180.0

    # 2. Test POST /api/vision/label
    files = {"file": ("label.jpg", img_data, "image/jpeg")}
    response = client.post("/api/vision/label", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["food_name"] == "Greek Yogurt"
    assert data["image_url"] == "/labels/reconstructed_Greek_Yogurt.png"

    # 3. Test Invalid file type error
    bad_files = {"file": ("document.txt", b"plain text", "text/plain")}
    bad_response = client.post("/api/vision/meal", files=bad_files)
    assert bad_response.status_code == 400
    assert "Unsupported file type" in bad_response.json()["detail"]

    app.dependency_overrides.clear()
