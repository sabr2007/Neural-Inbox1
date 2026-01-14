# tests/test_image_analyzer.py
"""Tests for Image Analyzer."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.image_analyzer import ImageAnalyzer, SUPPORTED_FORMATS
from src.config import MAX_IMAGE_SIZE


class TestImageAnalyzer:
    """Tests for ImageAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create ImageAnalyzer with mocked client."""
        with patch('src.services.image_analyzer.AsyncOpenAI'):
            return ImageAnalyzer()

    @pytest.fixture
    def temp_image_file(self):
        """Create temporary image file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            # Write minimal JPEG header
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 100)
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    @pytest.fixture
    def mock_vision_response(self):
        """Create mock Vision API response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Extracted text from image"
        return response

    @pytest.mark.asyncio
    async def test_analyze_success(self, analyzer, temp_image_file, mock_vision_response):
        """Test successful image analysis."""
        analyzer.client.chat.completions.create = AsyncMock(return_value=mock_vision_response)

        result = await analyzer.analyze(temp_image_file)

        assert result.is_error is False
        assert result.text == "Extracted text from image"
        assert result.source_type == "image"
        assert result.metadata["format"] == ".jpg"

    @pytest.mark.asyncio
    async def test_analyze_with_caption(self, analyzer, temp_image_file, mock_vision_response):
        """Test analysis with user caption."""
        analyzer.client.chat.completions.create = AsyncMock(return_value=mock_vision_response)

        result = await analyzer.analyze(temp_image_file, caption="My photo")

        assert result.is_error is False
        assert "[Подпись: My photo]" in result.text
        assert result.title == "My photo"
        assert result.metadata["has_caption"] is True

    @pytest.mark.asyncio
    async def test_analyze_unsupported_format(self, analyzer):
        """Test with unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            f.write(b"fake data")
            path = Path(f.name)

        try:
            result = await analyzer.analyze(path)
            assert result.is_error is True
            assert "не поддерживается" in result.error
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_not_found(self, analyzer):
        """Test with missing file."""
        result = await analyzer.analyze("/nonexistent/image.jpg")

        assert result.is_error is True
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_analyze_file_too_large(self, analyzer):
        """Test with oversized file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = Path(f.name)

        try:
            # Mock file size check
            with patch.object(Path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = MAX_IMAGE_SIZE + 1000

                result = await analyzer.analyze(path)

                assert result.is_error is True
                assert "слишком большое" in result.error
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_analyze_api_error(self, analyzer, temp_image_file):
        """Test API error handling."""
        analyzer.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Vision API Error")
        )

        result = await analyzer.analyze(temp_image_file)

        assert result.is_error is True
        assert "Ошибка" in result.error

    @pytest.mark.asyncio
    async def test_analyze_empty_response(self, analyzer, temp_image_file):
        """Test empty API response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = ""
        analyzer.client.chat.completions.create = AsyncMock(return_value=response)

        result = await analyzer.analyze(temp_image_file)

        assert result.is_error is True
        assert "проанализировать" in result.error

    def test_supported_formats(self):
        """Test supported formats constant."""
        assert '.jpg' in SUPPORTED_FORMATS
        assert '.jpeg' in SUPPORTED_FORMATS
        assert '.png' in SUPPORTED_FORMATS
        assert '.gif' in SUPPORTED_FORMATS
        assert '.webp' in SUPPORTED_FORMATS

    @pytest.mark.asyncio
    async def test_analyze_png_file(self, analyzer, mock_vision_response):
        """Test analysis of PNG file."""
        analyzer.client.chat.completions.create = AsyncMock(return_value=mock_vision_response)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            path = Path(f.name)

        try:
            result = await analyzer.analyze(path)
            assert result.is_error is False
            assert result.metadata["format"] == ".png"
        finally:
            path.unlink()
