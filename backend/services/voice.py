from elevenlabs import ElevenLabs
import os
import logging

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        self.api_key = os.getenv("ELEVEN_API_KEY")
        if not self.api_key:
            logger.warning("ELEVEN_API_KEY not set. Voice generation will fail.")
        
        self.client = ElevenLabs(api_key=self.api_key)
        # Default voice ID (Adam) if not specified
        self.voice_id = os.getenv("ELEVEN_VOICE_ID", "pNInz6obpgDQGcFmaJgB") 

    def generate_audio(self, text: str) -> bytes:
        if not self.api_key:
            raise ValueError("ELEVEN_API_KEY is missing.")

        try:
            # Generate audio stream using newer SDK syntax
            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_multilingual_v2"
            )
            
            # Combine generator into bytes
            audio_bytes = b"".join(audio_generator)
            return audio_bytes
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise

voice_service = VoiceService()
