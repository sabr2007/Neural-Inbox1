# tests/test_whisper_transcriber.py
"""Tests for Whisper Transcriber."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.whisper_transcriber import WhisperTranscriber
from src.config import MAX_VOICE_DURATION


class TestWhisperTranscriber:
    """Tests for WhisperTranscriber class."""

    @pytest.fixture
    def transcriber(self):
        """Create WhisperTranscriber with mocked client."""
        with patch('src.services.whisper_transcriber.AsyncOpenAI'):
            return WhisperTranscriber()

    @pytest.fixture
    def temp_audio_file(self):
        """Create temporary audio file."""
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(b"fake audio data")
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    @pytest.mark.asyncio
    async def test_transcribe_success(self, transcriber, temp_audio_file):
        """Test successful transcription."""
        transcriber.client.audio.transcriptions.create = AsyncMock(
            return_value="Привет, это тестовое сообщение"
        )

        result = await transcriber.transcribe(temp_audio_file, duration=10)

        assert result.is_error is False
        assert result.text == "Привет, это тестовое сообщение"
        assert result.source_type == "voice"
        assert result.metadata["duration"] == 10
        assert result.metadata["language"] == "ru"

    @pytest.mark.asyncio
    async def test_transcribe_duration_exceeded(self, transcriber, temp_audio_file):
        """Test transcription fails for long audio."""
        result = await transcriber.transcribe(
            temp_audio_file,
            duration=MAX_VOICE_DURATION + 100
        )

        assert result.is_error is True
        assert "слишком длинное" in result.error
        assert str(MAX_VOICE_DURATION) in result.error

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found(self, transcriber):
        """Test transcription with missing file."""
        result = await transcriber.transcribe("/nonexistent/file.ogg")

        assert result.is_error is True
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_transcribe_empty_result(self, transcriber, temp_audio_file):
        """Test transcription returns empty text."""
        transcriber.client.audio.transcriptions.create = AsyncMock(return_value="")

        result = await transcriber.transcribe(temp_audio_file)

        assert result.is_error is True
        assert "распознать" in result.error

    @pytest.mark.asyncio
    async def test_transcribe_api_error(self, transcriber, temp_audio_file):
        """Test API error handling."""
        transcriber.client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await transcriber.transcribe(temp_audio_file)

        assert result.is_error is True
        assert "Ошибка" in result.error

    @pytest.mark.asyncio
    async def test_transcribe_custom_language(self, transcriber, temp_audio_file):
        """Test transcription with custom language."""
        transcriber.client.audio.transcriptions.create = AsyncMock(
            return_value="Hello, this is a test"
        )

        result = await transcriber.transcribe(temp_audio_file, language="en")

        assert result.is_error is False
        assert result.metadata["language"] == "en"

    @pytest.mark.asyncio
    async def test_transcribe_without_duration(self, transcriber, temp_audio_file):
        """Test transcription without duration check."""
        transcriber.client.audio.transcriptions.create = AsyncMock(
            return_value="Test message"
        )

        result = await transcriber.transcribe(temp_audio_file)

        assert result.is_error is False
        assert result.metadata["duration"] is None
