from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from backend.services.voice import voice_service
from backend.api.security import get_current_user

router = APIRouter()

class SpeakRequest(BaseModel):
    text: str

@router.post("/speak")
async def speak(
    request: SpeakRequest,
    current_user: dict = Depends(get_current_user)
):
    """Convert text to speech."""
    try:
        audio_bytes = voice_service.generate_audio(request.text)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
