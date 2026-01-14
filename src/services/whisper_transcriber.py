"""
Whisper Transcriber - transcribes voice messages using OpenAI Whisper API.
"""
import logging
from pathlib import Path

from openai import AsyncOpenAI

from src.config import config, MAX_VOICE_DURATION
from src.services.extracted_content import ExtractedContent

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Transcribes audio files using OpenAI Whisper API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)

    async def transcribe(
        self,
        file_path: str | Path,
        language: str = "ru",
        duration: int | None = None
    ) -> ExtractedContent:
        """
        Transcribe audio file to text.

        Args:
            file_path: Path to audio file (.ogg, .mp3, .wav, etc.)
            language: Language hint for transcription
            duration: Audio duration in seconds (for validation)

        Returns:
            ExtractedContent with transcribed text
        """
        file_path = Path(file_path)

        # Validate duration if provided
        if duration is not None and duration > MAX_VOICE_DURATION:
            return ExtractedContent.from_error(
                f"Голосовое сообщение слишком длинное ({duration} сек). "
                f"Максимум: {MAX_VOICE_DURATION} сек (5 минут)",
                source_type="voice"
            )

        # Check file exists
        if not file_path.exists():
            return ExtractedContent.from_error(
                "Файл не найден", source_type="voice"
            )

        try:
            with open(file_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="text"
                )

            text = response.strip() if isinstance(response, str) else str(response).strip()

            if not text:
                return ExtractedContent.from_error(
                    "Не удалось распознать речь", source_type="voice"
                )

            return ExtractedContent(
                text=text,
                title=None,
                source_type="voice",
                metadata={
                    "duration": duration,
                    "language": language,
                }
            )

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ExtractedContent.from_error(
                f"Ошибка распознавания речи: {str(e)}", source_type="voice"
            )
