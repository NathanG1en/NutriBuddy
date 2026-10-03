# backend/api/routes/vision.py
"""API routes for Multimodal Vision Ingestion Pipeline."""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from typing import Optional

from backend.dependencies import get_vision_service
from backend.services.vision import VisionService
from backend.api.security import get_current_user

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


def _validate_image_file(file: UploadFile) -> None:
    """Validate content type and filename."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES and not any(
        file.filename.lower().endswith(ext)
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".heic"]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{content_type}'. Please upload a JPEG, PNG, or WebP image.",
        )


@router.post("/meal")
async def analyze_meal_photo(
    file: UploadFile = File(...),
    notes: Optional[str] = Form(""),
    vision_service: VisionService = Depends(get_vision_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a meal photograph:
    - Identifies food components and estimated portion sizes with Gemini Vision.
    - Resolves ingredients against USDA FoodData Central.
    - Returns verified macro totals, ingredient breakdowns, and dietary tags.
    """
    _validate_image_file(file)

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        result = await vision_service.analyze_meal_async(
            image_bytes=image_bytes,
            user_notes=notes or "",
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Meal image analysis failed: {str(e)}",
        )


@router.post("/label")
async def extract_and_reconstruct_label(
    file: UploadFile = File(...),
    vision_service: VisionService = Depends(get_vision_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a photograph of a physical FDA Nutrition Facts label:
    - Extracts nutrients and serving information with Gemini Vision OCR.
    - Automatically renders a pixel-accurate digital FDA label image.
    - Returns structured nutrients and digital image URL.
    """
    _validate_image_file(file)

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        result = await vision_service.extract_and_reconstruct_label_async(
            image_bytes=image_bytes,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Label extraction failed: {str(e)}",
        )
